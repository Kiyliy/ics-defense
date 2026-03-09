"""
Agent 主循环 — Plan-then-Act 模式，调用 XAI (Grok) API 进行工控安全告警分析。

核心流程:
  1. 规划阶段: 调用 LLM 生成分析计划
  2. 执行阶段: ReAct 循环，通过 MCP 调用工具
  3. 总结阶段: 解析最终决策，审计日志，触发钩子
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from openai import OpenAI

from agent.mcp_client import MCPClient, create_client_from_config
from agent.guard import AgentGuard, GuardException, MaxStepsExceeded, TotalTimeoutExceeded, AgentStuck
from agent.policy import ToolPolicy
from agent.audit import AuditLogger
from agent.hooks import HookManager
from agent.planner import AnalysisPlan, format_planning_prompt, format_execution_prompt
from agent.memory import AgentMemory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

DEFAULT_MODEL = os.environ.get("XAI_MODEL", "grok-3-mini-fast")
DEFAULT_BASE_URL = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")
DEFAULT_DB_PATH = "./data/ics-defense.db"
DEFAULT_GUARD_CONFIG = {
    "max_steps": 20,
    "total_timeout": 300,
    "max_retries": 2,
    "step_timeout": 30,
    "stuck_threshold": 3,
}

# 系统提示词文件路径
_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

PLANNING_RESPONSE_SCHEMA = {
    "name": "analysis_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "goal": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "integer"},
                        "action": {"type": "string"},
                        "tool": {"type": ["string", "null"]},
                    },
                    "required": ["id", "action", "tool"],
                },
            },
            "estimated_risk": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical", "unknown"],
            },
        },
        "required": ["goal", "steps", "estimated_risk"],
    },
}

DECISION_RESPONSE_SCHEMA = {
    "name": "analysis_decision",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical", "unknown"],
            },
            "confidence": {"type": "number"},
            "attack_chain": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "stage": {"type": "string"},
                        "technique": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["stage", "technique", "evidence"],
                },
            },
            "recommendation": {"type": "string"},
            "action_type": {
                "type": "string",
                "enum": ["block", "isolate", "monitor", "investigate", "manual_review"],
            },
            "rationale": {"type": "string"},
        },
        "required": [
            "risk_level",
            "confidence",
            "attack_chain",
            "recommendation",
            "action_type",
            "rationale",
        ],
    },
}


def _load_system_prompt() -> str:
    """加载系统提示词"""
    path = _PROMPT_DIR / "system.txt"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("系统提示词文件不存在: %s，使用默认提示词", path)
        return "你是一个工控安全分析 Agent。请分析告警并给出处置建议。"


def _load_planning_system_prompt() -> str:
    """加载规划阶段系统提示词"""
    path = _PROMPT_DIR / "planning.txt"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "请为以下告警制定分析计划，以 JSON 格式输出。"


def _create_structured_completion(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict[str, Any]],
    schema: dict[str, Any],
    max_tokens: int,
    temperature: float,
):
    """调用兼容 OpenAI 的 structured outputs 接口。"""
    return client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": schema,
        },
    )


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
    """确保 approval_queue 表存在"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approval_queue (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id     TEXT NOT NULL,
            tool_name    TEXT NOT NULL,
            tool_args    TEXT,
            reason       TEXT,
            status       TEXT DEFAULT 'pending',
            responded_at TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def _insert_approval_request(
    db_path: str,
    trace_id: str,
    tool_name: str,
    tool_args: dict,
    reason: str = "",
) -> int:
    """插入审批请求，返回记录 ID"""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        """
        INSERT INTO approval_queue (trace_id, tool_name, tool_args, reason, status)
        VALUES (?, ?, ?, ?, 'pending')
        """,
        (trace_id, tool_name, json.dumps(tool_args, ensure_ascii=False), reason),
    )
    approval_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return approval_id


def _check_approval_status(db_path: str, approval_id: int) -> Optional[str]:
    """查询审批状态，返回 'approved' | 'rejected' | None（仍在等待）"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status FROM approval_queue WHERE id = ?", (approval_id,)
    ).fetchone()
    conn.close()
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
# 解析最终决策
# ---------------------------------------------------------------------------

def parse_decision(response_content) -> dict:
    """从 LLM 响应中提取 JSON 格式的决策

    支持多种输入:
    - OpenAI 格式: 字符串 (message.content)
    - Anthropic 格式: content blocks 列表 (兼容旧格式)

    Returns:
        解析后的决策字典，如果解析失败返回默认决策
    """
    # 处理不同格式的输入
    if isinstance(response_content, str):
        full_text = response_content
    elif isinstance(response_content, list):
        text_parts = []
        for block in response_content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block["text"])
            elif hasattr(block, "type") and block.type == "text" and hasattr(block, "text"):
                text_parts.append(block.text)
        full_text = "\n".join(text_parts)
    else:
        full_text = str(response_content) if response_content else ""

    if not full_text.strip():
        return _default_decision("响应内容为空")

    # 尝试直接解析整个文本为 JSON
    try:
        return json.loads(full_text.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    # 尝试从 Markdown code block 中提取 JSON
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", full_text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试查找最外层 JSON 对象
    start = 0
    while True:
        brace_start = full_text.find("{", start)
        if brace_start == -1:
            break
        depth = 0
        for i in range(brace_start, len(full_text)):
            if full_text[i] == "{":
                depth += 1
            elif full_text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(full_text[brace_start:i + 1])
                        if isinstance(parsed, dict) and "risk_level" in parsed:
                            return parsed
                        return parsed
                    except json.JSONDecodeError:
                        pass
                    break
        start = brace_start + 1

    return _default_decision(f"无法从响应中解析 JSON 决策: {full_text[:200]}")


def _default_decision(reason: str) -> dict:
    """生成默认决策（解析失败时使用）"""
    return {
        "risk_level": "unknown",
        "confidence": 0.0,
        "attack_chain": [],
        "recommendation": "自动分析未能生成有效结论，请人工审查",
        "action_type": "manual_review",
        "rationale": reason,
    }


# ---------------------------------------------------------------------------
# Agent 主循环
# ---------------------------------------------------------------------------

async def agent_loop(
    clustered_alerts: list[dict],
    *,
    mcp_client: MCPClient | None = None,
    model: str | None = None,
    db_path: str | None = None,
    guard_config: dict | None = None,
    policy_config_path: str = "agent/tool_policy.yaml",
    hooks_config_path: str = "agent/hooks.yaml",
    memory_config: dict | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    trace_id: str | None = None,
) -> dict:
    """Agent 主循环 — 分析聚簇告警并返回决策

    Args:
        clustered_alerts: 聚簇后的告警列表
        mcp_client: MCP 客户端（可选，不传则自动创建）
        model: LLM 模型名称
        db_path: SQLite 数据库路径
        guard_config: Guard 配置
        policy_config_path: 工具策略配置路径
        hooks_config_path: 钩子配置路径
        memory_config: 记忆模块配置
        api_key: XAI API Key
        base_url: XAI API Base URL

    Returns:
        决策字典，包含 risk_level, confidence, attack_chain, recommendation 等
    """
    # --- 初始化 ---
    trace_id = trace_id or str(uuid4())
    db_path = db_path or os.environ.get("DB_PATH", DEFAULT_DB_PATH)
    model = model or DEFAULT_MODEL
    base_url = base_url or DEFAULT_BASE_URL

    # 创建 OpenAI 客户端（兼容 XAI API）
    client = OpenAI(
        api_key=api_key or os.environ.get("XAI_API_KEY"),
        base_url=base_url,
    )
    guard = AgentGuard(guard_config or DEFAULT_GUARD_CONFIG)
    guard.reset()

    try:
        policy = ToolPolicy(policy_config_path)
    except Exception as exc:
        logger.warning("加载工具策略失败: %s，使用默认策略", exc)
        policy = None

    audit = AuditLogger(db_path)

    try:
        hooks = HookManager(hooks_config_path)
    except Exception as exc:
        logger.warning("加载钩子配置失败: %s", exc)
        hooks = None

    memory = AgentMemory(memory_config or {"provider": "simple"})

    # 确保审批表存在
    _ensure_approval_table(db_path)

    # 是否需要自行管理 MCP 客户端生命周期
    own_mcp = mcp_client is None
    mcp = mcp_client

    try:
        # 如果没有传入 MCP 客户端，尝试自动创建
        if own_mcp:
            try:
                mcp = create_client_from_config()
                await mcp.connect_all()
                await mcp.refresh_tools()
            except Exception as exc:
                logger.warning("MCP 客户端创建失败: %s，将以无工具模式运行", exc)
                mcp = None

        # --- 审计: 分析开始 ---
        audit.log(trace_id, "analysis_started", {
            "alert_count": len(clustered_alerts),
            "model": model,
        })

        # --- Hook: on_alert_received ---
        if hooks:
            await hooks.trigger("on_alert_received", {
                "trace_id": trace_id,
                "alert_count": len(clustered_alerts),
                "alerts": clustered_alerts,
            })

        # ---------------------------------------------------------------
        # Phase 1: 记忆检索
        # ---------------------------------------------------------------
        memories = []
        try:
            query_parts = []
            for alert in clustered_alerts[:3]:
                sample = alert.get("sample", alert)
                if isinstance(sample, dict):
                    title = sample.get("title", "")
                    desc = sample.get("description", "")
                    query_parts.append(f"{title} {desc}")
            query = " ".join(query_parts).strip() or "安全告警分析"
            memories = await memory.recall(query, top_k=5)
            logger.info("检索到 %d 条相关历史记忆", len(memories))
        except Exception as exc:
            logger.warning("记忆检索失败: %s", exc)

        # ---------------------------------------------------------------
        # Phase 2: 规划 — 调用 LLM 生成分析计划
        # ---------------------------------------------------------------
        system_prompt = _load_system_prompt()
        planning_system = _load_planning_system_prompt()
        planning_prompt = format_planning_prompt(clustered_alerts, memories or None)

        logger.info("[%s] 开始规划阶段", trace_id)
        planning_response = _create_structured_completion(
            client,
            model=model,
            max_tokens=2048,
            temperature=0.2,
            schema=PLANNING_RESPONSE_SCHEMA,
            messages=[
                {"role": "system", "content": f"{system_prompt}\n\n{planning_system}"},
                {"role": "user", "content": planning_prompt},
            ],
        )

        # 提取规划文本
        plan_text = planning_response.choices[0].message.content or ""

        plan = AnalysisPlan.from_llm_response(plan_text)

        # 审计: 规划完成
        audit.log(
            trace_id,
            "plan_generated",
            plan.to_dict(),
            token_usage={
                "input_tokens": getattr(planning_response.usage, 'prompt_tokens', 0),
                "output_tokens": getattr(planning_response.usage, 'completion_tokens', 0),
            },
        )

        # Hook: on_plan_generated
        if hooks:
            await hooks.trigger("on_plan_generated", {
                "trace_id": trace_id,
                "plan": plan.to_dict(),
            })

        logger.info("[%s] 规划完成: %s", trace_id, plan.goal)

        # ---------------------------------------------------------------
        # Phase 3: 执行 — ReAct 循环
        # ---------------------------------------------------------------
        execution_prompt = format_execution_prompt(clustered_alerts, plan)
        raw_tools = mcp.list_tools_for_claude() if mcp else []
        openai_tools = _convert_tools_to_openai(raw_tools) if raw_tools else []

        # 构建执行消息列表
        exec_messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": execution_prompt},
        ]

        last_content = None

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

            # 没有工具调用 → 分析完成
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

            # 处理每个工具调用 —— 预处理：策略检查、审批、死循环检测
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
                    result = await guard.execute_with_retry(
                        mcp.call_tool, t_name, t_input,
                    )
                else:
                    result = {"error": "MCP 客户端不可用，无法执行工具调用"}
                if isinstance(result, dict):
                    r_str = json.dumps(result, ensure_ascii=False)
                else:
                    r_str = str(result)
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

        # ---------------------------------------------------------------
        # Phase 4: 总结 — 解析决策
        # ---------------------------------------------------------------
        decision = _default_decision("未获得模型响应")
        try:
            summary_messages = list(exec_messages)
            if last_content:
                summary_messages.append({"role": "assistant", "content": last_content})
            summary_messages.append({
                "role": "user",
                "content": (
                    "请基于以上完整分析过程输出最终结论。"
                    "必须严格遵守 JSON Schema，禁止输出 Markdown、代码块或额外说明。"
                ),
            })

            summary_response = _create_structured_completion(
                client,
                model=model,
                max_tokens=2048,
                temperature=0.1,
                schema=DECISION_RESPONSE_SCHEMA,
                messages=summary_messages,
            )
            summary_content = summary_response.choices[0].message.content or ""
            decision = parse_decision(summary_content)

            audit.log(
                trace_id,
                "llm_summary_call",
                {"finish_reason": summary_response.choices[0].finish_reason},
                token_usage={
                    "input_tokens": getattr(summary_response.usage, 'prompt_tokens', 0),
                    "output_tokens": getattr(summary_response.usage, 'completion_tokens', 0),
                },
            )
        except Exception as exc:
            logger.warning("[%s] 结构化总结失败，回退到兜底解析: %s", trace_id, exc)
            if last_content:
                decision = parse_decision(last_content)

        decision["trace_id"] = trace_id

        # 审计: 决策
        audit.log(trace_id, "decision_made", decision)

        # 总 token 统计
        total_tokens = audit.get_total_tokens(trace_id)
        decision["token_usage"] = total_tokens

        # Hook: on_decision_made
        if hooks:
            await hooks.trigger("on_decision_made", {
                "trace_id": trace_id,
                "decision": decision,
            })

        # 存储记忆
        try:
            summary = (
                f"告警分析: 风险等级={decision.get('risk_level', 'unknown')}, "
                f"建议={decision.get('recommendation', '')}"
            )
            await memory.memorize(summary, metadata={
                "trace_id": trace_id,
                "risk_level": decision.get("risk_level"),
                "category": "分析经验",
            })
        except Exception as exc:
            logger.warning("存储记忆失败: %s", exc)

        # 审计: 分析结束
        audit.log(trace_id, "analysis_finished", {
            "risk_level": decision.get("risk_level"),
            "token_usage": total_tokens,
        })

        # Hook: on_loop_finished
        if hooks:
            await hooks.trigger("on_loop_finished", {
                "trace_id": trace_id,
                "decision": decision,
                "token_usage": total_tokens,
            })

        logger.info("[%s] 分析完成: risk_level=%s", trace_id, decision.get("risk_level"))
        return decision

    except GuardException as exc:
        # Guard 异常 — 返回降级决策
        logger.error("[%s] Guard 异常: %s", trace_id, exc)
        fallback = _default_decision(f"Guard 异常: {exc}")
        fallback["trace_id"] = trace_id
        fallback["error"] = str(exc)
        fallback["error_type"] = type(exc).__name__

        audit.log(trace_id, "guard_exception", {
            "type": type(exc).__name__,
            "message": str(exc),
        })
        audit.log(trace_id, "analysis_finished", {
            "risk_level": "unknown",
            "error": str(exc),
        })

        if hooks:
            await hooks.trigger("on_error", {
                "trace_id": trace_id,
                "error": str(exc),
            })
            await hooks.trigger("on_loop_finished", {
                "trace_id": trace_id,
                "decision": fallback,
            })

        return fallback

    except Exception as exc:
        # 未预期异常
        logger.exception("[%s] 未预期异常: %s", trace_id, exc)
        fallback = _default_decision(f"内部错误: {exc}")
        fallback["trace_id"] = trace_id
        fallback["error"] = str(exc)

        try:
            audit.log(trace_id, "error", {
                "type": type(exc).__name__,
                "message": str(exc),
            })
            audit.log(trace_id, "analysis_finished", {
                "risk_level": "unknown",
                "error": str(exc),
            })
        except Exception:
            pass

        if hooks:
            try:
                await hooks.trigger("on_error", {
                    "trace_id": trace_id,
                    "error": str(exc),
                })
            except Exception:
                pass

        return fallback

    finally:
        # 清理资源
        try:
            audit.close()
        except Exception:
            pass

        if own_mcp and mcp:
            try:
                await mcp.close()
            except Exception:
                pass
