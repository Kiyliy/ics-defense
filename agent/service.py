"""
FastAPI 服务 — ICS Defense 统一 API 服务。

提供 REST API：
  - POST /analyze      启动告警分析
  - GET  /analyze/{id} 查询分析进度/结果
  - POST /chat         与 LLM 直接对话
  - GET  /status       健康检查
  - POST /approval/{id}/respond  审批响应
  - /api/alerts/*       告警管理
  - /api/analysis/*     分析与攻击链
  - /api/approval/*     审批管理
  - /api/audit/*        审计日志
  - /api/dashboard/*    指挥面板
  - /api/notifications/* 通知服务
  - /api/config/*       系统配置
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from openai import AsyncOpenAI
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from agent.db import get_db, init_db, get_sys_config
from agent.agent import agent_loop, DEFAULT_MODEL, DEFAULT_BASE_URL
from agent.audit import AuditLogger
from agent.mcp_client import MCPClient, create_client_from_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置
#   - 环境变量: 启动必须的 (DB_PATH, PORT) 和敏感信息 (API_KEY, AUTH_TOKEN)
#   - system_config 表: 运行时可调的 (model, base_url, cors, guard 等)
# ---------------------------------------------------------------------------

# 启动配置 (环境变量)
DB_PATH = os.environ.get("DB_PATH", "data/ics_defense.db")
MCP_CONFIG_PATH = os.environ.get("MCP_CONFIG_PATH", "agent/mcp_servers.yaml")
def _get_api_auth_token() -> str:
    """从 system_config 表读取 API 认证 token。"""
    return get_sys_config("api_auth_token", "", DB_PATH)


def _get_llm_model() -> str:
    """从 system_config 表读取 LLM 模型，支持运行时切换。"""
    return get_sys_config("llm_model", DEFAULT_MODEL, DB_PATH)


def _get_llm_base_url() -> str:
    """从 system_config 表读取 LLM base_url，支持运行时切换。"""
    return get_sys_config("llm_base_url", DEFAULT_BASE_URL, DB_PATH)


def _get_api_key() -> str:
    """从 system_config 表读取 LLM API Key。"""
    return get_sys_config("xai_api_key", "", DB_PATH)

# 全局状态
_mcp_client: Optional[MCPClient] = None
_running_tasks: dict[str, dict[str, Any]] = {}  # trace_id -> {task, status, result}

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """分析请求"""
    alert_ids: list[int] = Field(..., min_length=1, description="需要分析的告警 ID 列表")
    model: str | None = Field(default=None, description="使用的 LLM 模型，为空则从 system_config 读取")


class AnalyzeResponse(BaseModel):
    """分析响应"""
    trace_id: str
    status: str = "started"
    message: str = "分析任务已启动"


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str
    content: str


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: list[ChatMessage]
    model: str | None = Field(default=None, description="使用的 LLM 模型，为空则从 system_config 读取")


class ChatResponse(BaseModel):
    """聊天响应"""
    content: str
    usage: dict


class ApprovalResponse(BaseModel):
    """审批响应"""
    status: str = Field(..., pattern=r"^(approved|rejected)$")
    reason: Optional[str] = None


class StatusResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    mcp_connected: bool = False
    mcp_servers: list[str] = []
    running_tasks: int = 0
    db_path: str = ""


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------

async def startup() -> None:
    """启动时初始化 MCP 客户端"""
    global _mcp_client
    _ensure_tasks_table(DB_PATH)
    try:
        _mcp_client = create_client_from_config(MCP_CONFIG_PATH)
        await _mcp_client.connect_all()
        await _mcp_client.refresh_tools()
        logger.info(
            "MCP 客户端已连接: %s",
            _mcp_client.get_connected_servers(),
        )
    except Exception as exc:
        logger.warning("MCP 客户端启动失败: %s，将以无工具模式运行", exc)
        _mcp_client = None


async def shutdown() -> None:
    """关闭时清理资源"""
    global _mcp_client
    if _mcp_client:
        try:
            await _mcp_client.close()
        except Exception:
            pass
        _mcp_client = None

    # 取消所有运行中的任务
    for trace_id, task_info in _running_tasks.items():
        task = task_info.get("task")
        if task and not task.done():
            task.cancel()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup()
    try:
        yield
    finally:
        await shutdown()


# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ICS Defense Agent Service",
    description="工控安全 AI Agent 分析服务",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter state
app.state.limiter = limiter

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

_cors_default = "http://localhost:5173,http://localhost:5174"
_cors_origins = get_sys_config("cors_origins", "", DB_PATH) or os.environ.get("CORS_ORIGINS", _cors_default)
if isinstance(_cors_origins, str):
    _cors_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Rate limit error handler
# ---------------------------------------------------------------------------

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return Response(
        content=json.dumps({"error": "Too many requests, please try again later"}),
        status_code=429,
        media_type="application/json",
    )


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

def _safe_compare(a: str, b: str) -> bool:
    """Constant-time string comparison."""
    return hmac.compare_digest(a.encode(), b.encode())


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Token-based authentication middleware.

    Skips auth for health endpoint and when API_AUTH_TOKEN is not set (dev mode).
    Accepts token via Authorization: Bearer <token> or X-API-Key header.
    """
    # Skip auth for health endpoint
    if request.url.path == "/api/health":
        return await call_next(request)

    # Skip auth if no token configured (dev mode)
    auth_token = _get_api_auth_token()
    if not auth_token:
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    api_key_header = request.headers.get("x-api-key", "")
    bearer_token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    token = bearer_token or api_key_header

    if not token or not _safe_compare(token, auth_token):
        return Response(
            content=json.dumps({"error": "Unauthorized: invalid or missing API token"}),
            status_code=401,
            media_type="application/json",
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

from agent.routers.alerts import router as alerts_router
from agent.routers.analysis import router as analysis_router
from agent.routers.approval import router as approval_router
from agent.routers.audit import router as audit_router
from agent.routers.dashboard import router as dashboard_router
from agent.routers.notifications import router as notifications_router
from agent.routers.config import router as config_router

app.include_router(alerts_router)
app.include_router(analysis_router)
app.include_router(approval_router)
app.include_router(audit_router)
app.include_router(dashboard_router)
app.include_router(notifications_router)
app.include_router(config_router)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _ensure_tasks_table(db_path: str) -> None:
    """确保所有表存在（通过统一数据层）"""
    init_db(db_path)


def _update_task_in_db(trace_id: str, status: str, result: str | None = None, error: str | None = None) -> None:
    """更新 analysis_tasks 表中的任务状态"""
    completed_at = datetime.now().isoformat() if status in ("completed", "error") else None
    with get_db(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE analysis_tasks
            SET status = ?, result = ?, error = ?, completed_at = ?
            WHERE trace_id = ?
            """,
            (status, result, error, completed_at, trace_id),
        )
        conn.commit()


def _get_task_from_db(trace_id: str) -> dict | None:
    """从 analysis_tasks 表查询任务状态"""
    with get_db(DB_PATH) as conn:
        row = conn.execute(
            "SELECT * FROM analysis_tasks WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        return dict(row) if row else None


def _fetch_alerts_by_ids(alert_ids: list[int]) -> list[dict]:
    """根据 ID 列表查询告警数据"""
    if not alert_ids:
        return []

    with get_db(DB_PATH) as conn:
        placeholders = ",".join("?" for _ in alert_ids)
        rows = conn.execute(
            f"SELECT * FROM alerts WHERE id IN ({placeholders})",
            alert_ids,
        ).fetchall()
        return [dict(row) for row in rows]


def _make_clustered_alerts(alerts: list[dict]) -> list[dict]:
    """将原始告警转为聚簇格式（简化版，用于 agent_loop 输入）"""
    if not alerts:
        return []

    clusters: dict[tuple[str, str, str, str], list[dict]] = {}
    for alert in alerts:
        title = alert.get("title", "unknown")
        signature = (
            title,
            alert.get("source", "unknown"),
            alert.get("src_ip", ""),
            alert.get("dst_ip", ""),
        )
        clusters.setdefault(signature, []).append(alert)

    result = []
    for signature_parts, group in clusters.items():
        title, source, src_ip, dst_ip = signature_parts
        sample = group[0]
        result.append({
            "signature": "|".join([title, source, src_ip or "-", dst_ip or "-"]),
            "sample": sample,
            "count": len(group),
            "severity": sample.get("severity", "medium"),
            "first_seen": group[0].get("created_at", ""),
            "last_seen": group[-1].get("created_at", ""),
            "source_ips": list({a.get("src_ip", "") for a in group if a.get("src_ip")}),
            "target_ips": list({a.get("dst_ip", "") for a in group if a.get("dst_ip")}),
        })

    return result


async def _run_analysis(trace_id: str, clustered_alerts: list[dict], model: str):
    """后台运行 Agent 分析任务"""
    try:
        _running_tasks[trace_id]["status"] = "running"
        _update_task_in_db(trace_id, status="running")
        result = await agent_loop(
            clustered_alerts,
            mcp_client=_mcp_client,
            model=model,
            db_path=DB_PATH,
            trace_id=trace_id,
        )
        _persist_analysis_result(trace_id, _running_tasks[trace_id].get("alert_ids", []), result)
        _running_tasks[trace_id]["status"] = "completed"
        _running_tasks[trace_id]["result"] = result
        _update_task_in_db(trace_id, status="completed", result=json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        logger.exception("分析任务异常: trace_id=%s", trace_id)
        _running_tasks[trace_id]["status"] = "error"
        _running_tasks[trace_id]["error"] = str(exc)
        _update_task_in_db(trace_id, status="error", error=str(exc))


def _persist_analysis_result(trace_id: str, alert_ids: list[int], result: dict) -> None:
    """将 Agent 分析结果写回业务表，便于前端统一查询。"""
    with get_db(DB_PATH) as conn:
        risk_level = result.get("risk_level", "unknown")
        confidence = float(result.get("confidence", 0))
        recommendation = result.get("recommendation", "")
        action_type = result.get("action_type", "investigate")
        rationale = result.get("rationale", "")

        # Build a meaningful chain name from the attack_chain's first technique
        attack_chain = result.get("attack_chain") or []
        first_technique = None
        first_stage = None
        if attack_chain and isinstance(attack_chain, list):
            entry = attack_chain[0] if isinstance(attack_chain[0], dict) else {}
            first_technique = entry.get("technique")
            first_stage = entry.get("stage")

        chain_name = f"{risk_level.upper()}: {first_technique or 'Alert Analysis'}"

        conn.execute(
            """
            INSERT INTO attack_chains (name, stage, confidence, alert_ids, evidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chain_name,
                first_stage or "unknown",
                confidence,
                json.dumps(alert_ids, ensure_ascii=False),
                rationale,
            ),
        )
        attack_chain_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            """
            INSERT INTO decisions (attack_chain_id, risk_level, recommendation, action_type, rationale)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                attack_chain_id,
                risk_level,
                recommendation,
                action_type,
                rationale,
            ),
        )

        conn.executemany(
            "UPDATE alerts SET status = ? WHERE id = ?",
            [("resolved", alert_id) for alert_id in alert_ids],
        )
        conn.commit()


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """启动告警分析任务"""
    try:
        alerts = _fetch_alerts_by_ids(request.alert_ids)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询告警失败: {exc}")

    if not alerts:
        raise HTTPException(status_code=404, detail="未找到指定告警")

    clustered = _make_clustered_alerts(alerts)
    trace_id = str(uuid4())

    loop = asyncio.get_running_loop()
    model = request.model or _get_llm_model()
    task = loop.create_task(_run_analysis(trace_id, clustered, model))

    started_at = datetime.now().isoformat()
    _running_tasks[trace_id] = {
        "task": task,
        "status": "started",
        "result": None,
        "error": None,
        "started_at": started_at,
        "alert_ids": request.alert_ids,
    }

    # Persist to DB so state survives restarts
    with get_db(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO analysis_tasks (trace_id, status, alert_ids, started_at) VALUES (?, ?, ?, ?)",
            (trace_id, "started", json.dumps(request.alert_ids), started_at),
        )
        conn.commit()

    return AnalyzeResponse(
        trace_id=trace_id,
        status="started",
        message=f"分析任务已启动，共 {len(alerts)} 条告警",
    )


@app.get("/analyze/{trace_id}")
async def get_analysis(trace_id: str):
    """查询分析进度和结果"""
    task_info = _running_tasks.get(trace_id)

    try:
        audit = AuditLogger(DB_PATH)
        logs = audit.get_trace(trace_id)
        total_tokens = audit.get_total_tokens(trace_id)
        audit.close()
    except Exception:
        logs = []
        total_tokens = {"input_tokens": 0, "output_tokens": 0, "total": 0}

    if task_info:
        return {
            "trace_id": trace_id,
            "status": task_info["status"],
            "result": task_info.get("result"),
            "error": task_info.get("error"),
            "started_at": task_info.get("started_at"),
            "alert_ids": task_info.get("alert_ids"),
            "audit_logs": logs,
            "token_usage": total_tokens,
        }

    # Fall back to DB for tasks from previous service runs
    db_task = _get_task_from_db(trace_id)
    if db_task:
        alert_ids = json.loads(db_task["alert_ids"]) if db_task["alert_ids"] else []
        result = json.loads(db_task["result"]) if db_task["result"] else None
        return {
            "trace_id": trace_id,
            "status": db_task["status"],
            "result": result,
            "error": db_task["error"],
            "started_at": db_task["started_at"],
            "completed_at": db_task["completed_at"],
            "alert_ids": alert_ids,
            "audit_logs": logs,
            "token_usage": total_tokens,
        }

    if logs:
        event_types = [log["event_type"] for log in logs]
        if "analysis_finished" in event_types:
            status = "completed"
        elif "error" in event_types or "guard_exception" in event_types:
            status = "error"
        else:
            status = "unknown"

        decision = None
        for log in reversed(logs):
            if log["event_type"] == "decision_made":
                decision = log.get("data")
                break

        return {
            "trace_id": trace_id,
            "status": status,
            "result": decision,
            "audit_logs": logs,
            "token_usage": total_tokens,
        }

    raise HTTPException(status_code=404, detail=f"未找到分析记录: {trace_id}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """与 LLM 直接对话（简单聊天接口）"""
    try:
        client = AsyncOpenAI(
            api_key=_get_api_key(),
            base_url=_get_llm_base_url(),
        )

        model = request.model or _get_llm_model()

        messages = [
            {"role": "system", "content": "你是一个工控安全分析助手。"},
        ] + [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        response = await client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=messages,
        )

        content = response.choices[0].message.content or ""

        return ChatResponse(
            content=content,
            usage={
                "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                "completion_tokens": getattr(response.usage, 'completion_tokens', 0),
            },
        )

    except Exception as exc:
        error_msg = str(exc)
        if "401" in error_msg or "auth" in error_msg.lower():
            raise HTTPException(status_code=401, detail="API Key 无效")
        elif "429" in error_msg or "rate" in error_msg.lower():
            raise HTTPException(status_code=429, detail="API 请求频率超限")
        raise HTTPException(status_code=500, detail=f"聊天请求失败: {exc}")


@app.get("/status", response_model=StatusResponse)
async def status():
    """健康检查"""
    mcp_connected = _mcp_client is not None
    mcp_servers = _mcp_client.get_connected_servers() if _mcp_client else []

    active_tasks = sum(
        1 for t in _running_tasks.values()
        if t["status"] in ("started", "running")
    )

    return StatusResponse(
        status="ok",
        mcp_connected=mcp_connected,
        mcp_servers=mcp_servers,
        running_tasks=active_tasks,
        db_path=DB_PATH,
    )


@app.get("/mcp/servers")
async def mcp_servers():
    """返回 MCP Server 列表及其工具定义"""
    import yaml

    # 读取配置获取 server 元信息
    try:
        with open(MCP_CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        server_configs = {s["name"]: s for s in config.get("servers", [])}
    except Exception:
        server_configs = {}

    # 读取 tool_policy
    policy_path = os.path.join(os.path.dirname(MCP_CONFIG_PATH), "tool_policy.yaml")
    tool_levels: dict[str, str] = {}
    try:
        with open(policy_path) as f:
            policy = yaml.safe_load(f)
        for level, tools in (policy.get("tool_levels") or {}).items():
            for tool_name in (tools or []):
                tool_levels[tool_name] = level
    except Exception:
        pass

    connected = _mcp_client.get_connected_servers() if _mcp_client else []
    tool_map = _mcp_client._tool_map if _mcp_client else {}
    tool_defs = _mcp_client.list_tools() if _mcp_client else []

    # 按 server 分组
    servers_dict: dict[str, dict] = {}
    for name in set(list(server_configs.keys()) + connected):
        cfg = server_configs.get(name, {})
        servers_dict[name] = {
            "name": name,
            "connected": name in connected,
            "command": cfg.get("command", ""),
            "args": cfg.get("args", []),
            "tools": [],
        }

    for tool in tool_defs:
        server_name = tool_map.get(tool["name"], "unknown")
        if server_name in servers_dict:
            servers_dict[server_name]["tools"].append({
                **tool,
                "policy": tool_levels.get(tool["name"], "auto"),
            })

    return {"servers": list(servers_dict.values())}


@app.post("/approval/{approval_id}/respond")
async def respond_approval(approval_id: int, response: ApprovalResponse):
    """审批响应 — 批准或拒绝工具调用"""
    with get_db(DB_PATH) as conn:
        row = conn.execute(
            "SELECT * FROM approval_queue WHERE id = ?", (approval_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"审批记录不存在: {approval_id}")

        if row["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"审批已处理: 当前状态={row['status']}",
            )

        conn.execute(
            """
            UPDATE approval_queue
            SET status = ?, responded_at = datetime('now')
            WHERE id = ?
            """,
            (response.status, approval_id),
        )
        conn.commit()

        logger.info(
            "审批响应: id=%d status=%s reason=%s",
            approval_id, response.status, response.reason,
        )

        return {
            "id": approval_id,
            "status": response.status,
            "reason": response.reason,
            "message": f"审批已{('批准' if response.status == 'approved' else '拒绝')}",
        }


# ---------------------------------------------------------------------------
# /api/ prefixed aliases for nginx compatibility (M7)
# The original routes are kept for backward compatibility.
# ---------------------------------------------------------------------------

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def api_analyze(request: AnalyzeRequest):
    """Alias for /analyze — reachable through nginx /api/ proxy."""
    return await analyze(request)


@app.get("/api/analyze/{trace_id}")
async def api_get_analysis(trace_id: str):
    """Alias for /analyze/{trace_id} — reachable through nginx /api/ proxy."""
    return await get_analysis(trace_id)


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(request: ChatRequest):
    """Alias for /chat — reachable through nginx /api/ proxy."""
    return await chat(request)


@app.get("/api/status", response_model=StatusResponse)
async def api_status():
    """Alias for /status — reachable through nginx /api/ proxy."""
    return await status()


@app.get("/api/mcp/servers")
async def api_mcp_servers():
    """Alias for /mcp/servers — reachable through nginx /api/ proxy."""
    return await mcp_servers()


@app.post("/api/approval/{approval_id}/respond")
async def api_respond_approval(approval_id: int, response: ApprovalResponse):
    """Alias for /approval/{id}/respond — reachable through nginx /api/ proxy."""
    return await respond_approval(approval_id, response)
