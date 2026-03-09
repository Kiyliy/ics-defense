"""规划阶段 — 记忆检索 + LLM 生成分析计划"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

from agent.audit import AuditLogger
from agent.hooks import HookManager
from agent.memory import AgentMemory
from agent.planner import AnalysisPlan, format_planning_prompt

logger = logging.getLogger(__name__)

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


async def recall_memories(
    clustered_alerts: list[dict],
    memory: AgentMemory,
) -> list[dict]:
    """从记忆模块检索相关历史分析

    Args:
        clustered_alerts: 聚簇告警列表
        memory: 记忆模块实例

    Returns:
        相关记忆列表
    """
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
        return memories
    except Exception as exc:
        logger.warning("记忆检索失败: %s", exc)
        return []


async def run_planning(
    clustered_alerts: list[dict],
    client: OpenAI,
    model: str,
    memory: AgentMemory,
    audit: AuditLogger,
    hooks: Optional[HookManager],
    trace_id: str,
) -> tuple[AnalysisPlan, list[dict], str]:
    """执行规划阶段：记忆检索 + LLM 生成分析计划

    Args:
        clustered_alerts: 聚簇告警列表
        client: OpenAI 兼容客户端
        model: 模型名称
        memory: 记忆模块
        audit: 审计日志
        hooks: 钩子管理器
        trace_id: 追踪 ID

    Returns:
        (plan, memories, system_prompt) 三元组
    """
    # --- 记忆检索 ---
    memories = await recall_memories(clustered_alerts, memory)

    # --- 规划 LLM 调用 ---
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

    return plan, memories, system_prompt
