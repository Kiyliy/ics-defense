"""执行阶段 — ReAct 循环，MCP 工具调用，策略检查，Guard 集成"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from openai import OpenAI

from agent.audit import AuditLogger
from agent.db import get_db, init_db
from agent.guard import AgentGuard, GuardException, AgentStuck
from agent.hooks import HookManager
from agent.mcp_client import MCPClient
from agent.planner import AnalysisPlan, format_execution_prompt
from agent.policy import ToolPolicy
from agent.types import ExecutionResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具格式转换
# ---------------------------------------------------------------------------

def _convert_tools_to_openai(tools: list[dict]) -> list[dict]:
    """将 MCP/Claude 格式的工具定义转换为 OpenAI 格式

    输入格式 (Claude): {"type": "custom", "name": "x", "description": "y", "input_schema": {...}}
    输出格式 (OpenAI): {"type": "function", "function": {"name": "x", "description": "y", "parameters": {...}}}
    """
    openai_tools = []
    for t in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            }
        })
    return openai_tools


# ---------------------------------------------------------------------------
# 审批队列操作（SQLite）
# ---------------------------------------------------------------------------

def _ensure_approval_table(db_path: str) -> None:
    """确保所有表存在（通过统一数据层）"""
    init_db(db_path)


def _insert_approval_request(
    db_path: str,
    trace_id: str,
    tool_name: str,
    tool_args: dict,
    reason: str = "",
) -> int:
    """插入审批请求，返回记录 ID"""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO approval_queue (trace_id, tool_name, tool_args, reason, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (trace_id, tool_name, json.dumps(tool_args, ensure_ascii=False), reason),
        )
        approval_id = cursor.lastrowid
        conn.commit()
    return approval_id


def _check_approval_status(db_path: str, approval_id: int) -> Optional[str]:
    """查询审批状态，返回 'approved' | 'rejected' | None（仍在等待）"""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT status FROM approval_queue WHERE id = ?", (approval_id,)
        ).fetchone()
    if row and row["status"] != "pending":
        return row["status"]
    return None


async def wait_for_approval(
    db_path: str,
    approval_id: int,
    timeout: int = 300,
    poll_interval: float = 2.0,
) -> str:
    """轮询等待审批结果

    Returns:
        "approved" | "rejected" | "timeout"
    """
    start = time.monotonic()
    while True:
        status = _check_approval_status(db_path, approval_id)
        if status is not None:
            return status
        elapsed = time.monotonic() - start
        if elapsed >= timeout:
            return "timeout"
        await asyncio.sleep(poll_interval)


# ---------------------------------------------------------------------------
# 执行阶段主函数
# ---------------------------------------------------------------------------

async def run_execution(
    clustered_alerts: list[dict],
    plan: AnalysisPlan,
    client: OpenAI,
    model: str,
    system_prompt: str,
    mcp: Optional[MCPClient],
    policy: Optional[ToolPolicy],
    guard: AgentGuard,
    hooks: Optional[HookManager],
    audit: AuditLogger,
    db_path: str,
    trace_id: str,
) -> ExecutionResult:
    """执行 ReAct 循环：LLM 推理 + 工具调用

    Args:
        clustered_alerts: 聚簇告警列表
        plan: 分析计划
        client: OpenAI 兼容客户端
        model: 模型名称
        system_prompt: 系统提示词
        mcp: MCP 客户端
        policy: 工具策略
        guard: 安全守卫
        hooks: 钩子管理器
        audit: 审计日志
        db_path: 数据库路径
        trace_id: 追踪 ID

    Returns:
        ExecutionResult 包含执行过程消息和最终内容
    """
    execution_prompt = format_execution_prompt(clustered_alerts, plan)
    raw_tools = mcp.list_tools_for_claude() if mcp else []
    openai_tools = _convert_tools_to_openai(raw_tools) if raw_tools else []

    # 构建执行消息列表
    exec_messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": execution_prompt},
    ]

    last_content = None
    result = ExecutionResult()

    logger.info("[%s] 开始执行阶段，共 %d 个工具可用", trace_id, len(openai_tools))

    while True:
        try:
            guard.check_before_step()
        except GuardException as exc:
            logger.warning("[%s] Guard 终止执行: %s", trace_id, exc)
            audit.log(trace_id, "guard_exception", {
                "type": type(exc).__name__,
                "message": str(exc),
            })
            if hooks:
                await hooks.trigger("on_error", {
                    "trace_id": trace_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                })
            result.terminated_by_guard = True
            result.guard_error = str(exc)
            break

        # 调用 LLM (OpenAI 格式)
        create_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "messages": exec_messages,
        }
        if openai_tools:
            create_kwargs["tools"] = openai_tools

        response = client.chat.completions.create(**create_kwargs)
        msg = response.choices[0].message

        # 审计: LLM 调用（包含模型回复内容）
        llm_log_data = {
            "finish_reason": response.choices[0].finish_reason,
        }
        if msg.content:
            llm_log_data["content"] = msg.content
        audit.log(
            trace_id,
            "llm_call",
            llm_log_data,
            token_usage={
                "input_tokens": getattr(response.usage, 'prompt_tokens', 0),
                "output_tokens": getattr(response.usage, 'completion_tokens', 0),
            },
        )

        # 保存最后的文本内容用于解析决策
        if msg.content:
            last_content = msg.content

        # 提取工具调用
        tool_calls = msg.tool_calls or []

        # 没有工具调用 -> 分析完成
        if not tool_calls:
            logger.info("[%s] 执行阶段完成（无更多工具调用）", trace_id)
            break

        # 将 assistant 响应添加到消息列表（OpenAI 格式）
        assistant_msg = {"role": "assistant", "content": msg.content}
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            }
            for tc in tool_calls
        ]
        exec_messages.append(assistant_msg)

        # 处理每个工具调用 -- 预处理：策略检查、审批、死循环检测
        pending_calls = []  # (tc, tool_name, tool_input, level) 通过预检的调用
        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                tool_input = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                tool_input = {}
            tool_call_id = tc.id

            logger.info("[%s] 调用工具: %s", trace_id, tool_name)

            # 检查工具策略
            level = policy.get_level(tool_name) if policy else "auto"

            # --- 审批流程 ---
            if level == "approve":
                logger.info("[%s] 工具 %s 需要人工审批", trace_id, tool_name)

                if hooks:
                    await hooks.trigger("on_approval_needed", {
                        "trace_id": trace_id,
                        "tool_name": tool_name,
                        "tool_args": tool_input,
                    })

                approval_id = _insert_approval_request(
                    db_path, trace_id, tool_name, tool_input,
                    reason=f"工具 {tool_name} 需要人工审批",
                )

                timeout = policy.approval_timeout if policy else 300
                approval_status = await wait_for_approval(
                    db_path, approval_id, timeout=timeout,
                )

                audit.log(trace_id, "approval_result", {
                    "approval_id": approval_id,
                    "tool_name": tool_name,
                    "status": approval_status,
                })

                if approval_status != "approved":
                    exec_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({
                            "error": f"工具调用被拒绝（状态: {approval_status}）"
                        }, ensure_ascii=False),
                    })
                    continue

            # --- 死循环检测 ---
            try:
                guard.check_stuck(tool_name, tool_input)
            except AgentStuck as exc:
                logger.warning("[%s] 检测到死循环: %s", trace_id, exc)
                audit.log(trace_id, "agent_stuck", {
                    "tool_name": tool_name,
                    "message": str(exc),
                })
                exec_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({
                        "error": f"检测到重复调用，请尝试其他方法: {exc}"
                    }, ensure_ascii=False),
                })
                continue

            pending_calls.append((tc, tool_name, tool_input, level))

        # --- 并发执行所有通过预检的 MCP 工具调用 ---
        async def _execute_single_tool(tc_item):
            """执行单个工具调用，返回 (tc, tool_name, tool_input, level, result_str)"""
            tc, t_name, t_input, t_level = tc_item
            if mcp:
                tool_result = await guard.execute_with_retry(
                    mcp.call_tool, t_name, t_input,
                )
            else:
                tool_result = {"error": "MCP 客户端不可用，无法执行工具调用"}
            if isinstance(tool_result, dict):
                r_str = json.dumps(tool_result, ensure_ascii=False)
            else:
                r_str = str(tool_result)
            return tc, t_name, t_input, t_level, r_str

        if pending_calls:
            # 并发执行所有工具调用
            call_results = await asyncio.gather(
                *[_execute_single_tool(item) for item in pending_calls],
                return_exceptions=True,
            )

            for cr in call_results:
                if isinstance(cr, Exception):
                    logger.error("[%s] 工具并发执行异常: %s", trace_id, cr)
                    continue

                tc, tool_name, tool_input, level, result_str = cr

                # 审计: 工具调用
                audit.log(trace_id, "tool_call", {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "result_preview": result_str[:500],
                    "policy_level": level,
                })

                # Hook: on_tool_called
                if hooks:
                    await hooks.trigger("on_tool_called", {
                        "trace_id": trace_id,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                    })

                # 通知级别：触发 on_tool_result 钩子
                if level == "notify" and hooks:
                    await hooks.trigger("on_tool_result", {
                        "trace_id": trace_id,
                        "tool_name": tool_name,
                        "result_preview": result_str[:200],
                    })

                # OpenAI 格式的工具结果
                exec_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

                # 更新计划步骤状态
                next_step = plan.get_next_pending()
                if next_step:
                    plan.mark_step(next_step.id, "completed", result_str[:100])

    result.last_content = last_content
    result.exec_messages = exec_messages
    return result
