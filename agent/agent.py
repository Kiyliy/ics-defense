"""
Agent 主循环 — Plan-then-Act 模式，调用 XAI (Grok) API 进行工控安全告警分析。

核心流程:
  1. 规划阶段: 调用 LLM 生成分析计划 (planning.py)
  2. 执行阶段: ReAct 循环，通过 MCP 调用工具 (executor.py)
  3. 总结阶段: 解析最终决策，审计日志，触发钩子 (conclusion.py)

本文件仅作为编排器，依次调用三个阶段并处理顶层异常。
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from uuid import uuid4

from openai import OpenAI

from agent.mcp_client import MCPClient, create_client_from_config
from agent.guard import AgentGuard, GuardException
from agent.policy import ToolPolicy
from agent.audit import AuditLogger
from agent.hooks import HookManager
from agent.memory import AgentMemory
from agent.db import get_sys_config

# Phase modules
from agent.planning import run_planning
from agent.executor import run_execution, _ensure_approval_table
from agent.conclusion import run_conclusion

# Re-export symbols used by tests and other modules so that
# ``from agent.agent import X`` continues to work unchanged.
from agent.planning import (                          # noqa: F401
    _load_system_prompt,
    _load_planning_system_prompt,
    _PROMPT_DIR,
    PLANNING_RESPONSE_SCHEMA,
)
from agent.executor import (                          # noqa: F401
    _convert_tools_to_openai,
    _insert_approval_request,
    _check_approval_status,
    wait_for_approval,
)
from agent.conclusion import (                        # noqa: F401
    parse_decision,
    _default_decision,
    DECISION_RESPONSE_SCHEMA,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

# 回退默认值
_FALLBACK_MODEL = "grok-3-mini-fast"
_FALLBACK_BASE_URL = "https://api.x.ai/v1"

# 启动配置（仅环境变量）
DEFAULT_DB_PATH = os.environ.get("DB_PATH", "data/ics_defense.db")

# 运行时配置：惰性读取 system_config 表，环境变量作为回退
DEFAULT_MODEL = os.environ.get("XAI_MODEL", _FALLBACK_MODEL)
DEFAULT_BASE_URL = os.environ.get("XAI_BASE_URL", _FALLBACK_BASE_URL)


def get_runtime_model(db_path: str | None = None) -> str:
    """从 system_config 表读取 LLM 模型（支持运行时热切换）。"""
    return get_sys_config("llm_model", "", db_path or DEFAULT_DB_PATH) or DEFAULT_MODEL


def get_runtime_base_url(db_path: str | None = None) -> str:
    """从 system_config 表读取 LLM base_url。"""
    return get_sys_config("llm_base_url", "", db_path or DEFAULT_DB_PATH) or DEFAULT_BASE_URL


def get_runtime_guard_config(db_path: str | None = None) -> dict:
    """从 system_config 表读取 guard 配置。"""
    db = db_path or DEFAULT_DB_PATH
    return {
        "max_steps": int(get_sys_config("guard_max_steps", "20", db)),
        "step_timeout": int(get_sys_config("guard_step_timeout", "30", db)),
        "total_timeout": int(get_sys_config("guard_total_timeout", "300", db)),
        "max_retries": int(get_sys_config("guard_max_retries", "2", db)),
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
        trace_id: 追踪 ID

    Returns:
        决策字典，包含 risk_level, confidence, attack_chain, recommendation 等
    """
    # --- 初始化 ---
    trace_id = trace_id or str(uuid4())
    db_path = db_path or DEFAULT_DB_PATH
    model = model or get_runtime_model(db_path)
    base_url = base_url or get_runtime_base_url(db_path)

    client = OpenAI(
        api_key=api_key or get_sys_config("xai_api_key", "", db_path),
        base_url=base_url,
    )
    guard = AgentGuard(guard_config or get_runtime_guard_config(db_path))
    guard.reset()

    try:
        policy: Optional[ToolPolicy] = ToolPolicy(policy_config_path)
    except Exception as exc:
        logger.warning("加载工具策略失败: %s，使用默认策略", exc)
        policy = None

    audit = AuditLogger(db_path)

    try:
        hooks: Optional[HookManager] = HookManager(hooks_config_path)
    except Exception as exc:
        logger.warning("加载钩子配置失败: %s", exc)
        hooks = None

    memory = AgentMemory(memory_config or {"provider": "simple"})

    _ensure_approval_table(db_path)

    own_mcp = mcp_client is None
    mcp = mcp_client

    try:
        # 自动创建 MCP 客户端
        if own_mcp:
            try:
                mcp = create_client_from_config()
                await mcp.connect_all()
                await mcp.refresh_tools()
            except Exception as exc:
                logger.warning("MCP 客户端创建失败: %s，将以无工具模式运行", exc)
                mcp = None

        # 审计: 分析开始
        audit.log(trace_id, "analysis_started", {
            "alert_count": len(clustered_alerts),
            "model": model,
        })

        # Hook: on_alert_received
        if hooks:
            await hooks.trigger("on_alert_received", {
                "trace_id": trace_id,
                "alert_count": len(clustered_alerts),
                "alerts": clustered_alerts,
            })

        # Phase 1: 规划
        plan, _memories, system_prompt = await run_planning(
            clustered_alerts, client, model, memory, audit, hooks, trace_id,
        )

        # Phase 2: 执行
        exec_result = await run_execution(
            clustered_alerts, plan, client, model, system_prompt,
            mcp, policy, guard, hooks, audit, db_path, trace_id,
        )

        # Phase 3: 总结
        decision = await run_conclusion(
            exec_result, client, model, memory, audit, hooks, trace_id,
        )

        return decision

    except GuardException as exc:
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
        try:
            audit.close()
        except Exception:
            pass

        if own_mcp and mcp:
            try:
                await mcp.close()
            except Exception:
                pass
