"""总结阶段 — 解析最终决策，存储记忆，触发完成钩子"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from openai import OpenAI

from agent.audit import AuditLogger
from agent.hooks import HookManager
from agent.memory import AgentMemory
from agent.types import ExecutionResult

logger = logging.getLogger(__name__)

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


from agent.llm_utils import create_structured_completion as _create_structured_completion


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
# 总结阶段主函数
# ---------------------------------------------------------------------------

async def run_conclusion(
    execution_result: ExecutionResult,
    client: OpenAI,
    model: str,
    memory: AgentMemory,
    audit: AuditLogger,
    hooks: Optional[HookManager],
    trace_id: str,
) -> dict:
    """执行总结阶段：解析决策 + 存储记忆 + 触发完成钩子

    Args:
        execution_result: 执行阶段结果
        client: OpenAI 兼容客户端
        model: 模型名称
        memory: 记忆模块
        audit: 审计日志
        hooks: 钩子管理器
        trace_id: 追踪 ID

    Returns:
        决策字典
    """
    decision = _default_decision("未获得模型响应")
    try:
        summary_messages = list(execution_result.exec_messages)
        if execution_result.last_content:
            summary_messages.append({"role": "assistant", "content": execution_result.last_content})
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
        if execution_result.last_content:
            decision = parse_decision(execution_result.last_content)

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
