"""
FastAPI 服务 — 连接 Express 后端和 Python Agent。

提供 REST API：
  - POST /analyze      启动告警分析
  - GET  /analyze/{id} 查询分析进度/结果
  - POST /chat         与 LLM 直接对话
  - GET  /status       健康检查
  - POST /approval/{id}/respond  审批响应
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from openai import OpenAI
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from agent.agent import agent_loop, DEFAULT_MODEL, DEFAULT_BASE_URL
from agent.audit import AuditLogger
from agent.mcp_client import MCPClient, create_client_from_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get("DB_PATH", "./data/ics-defense.db")
MCP_CONFIG_PATH = os.environ.get("MCP_CONFIG_PATH", "agent/mcp_servers.yaml")
LLM_MODEL = os.environ.get("XAI_MODEL", DEFAULT_MODEL)

# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ICS Defense Agent Service",
    description="工控安全 AI Agent 分析服务",
    version="1.0.0",
)

# 全局状态
_mcp_client: Optional[MCPClient] = None
_running_tasks: dict[str, dict[str, Any]] = {}  # trace_id -> {task, status, result}


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """分析请求"""
    alert_ids: list[int] = Field(..., description="需要分析的告警 ID 列表")
    model: str = Field(default=LLM_MODEL, description="使用的 LLM 模型")


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
    model: str = Field(default=LLM_MODEL, description="使用的 LLM 模型")


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

@app.on_event("startup")
async def startup():
    """启动时初始化 MCP 客户端"""
    global _mcp_client
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


@app.on_event("shutdown")
async def shutdown():
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


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _get_db_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_alerts_by_ids(alert_ids: list[int]) -> list[dict]:
    """根据 ID 列表查询告警数据"""
    conn = _get_db_connection()
    try:
        placeholders = ",".join("?" for _ in alert_ids)
        rows = conn.execute(
            f"SELECT * FROM alerts WHERE id IN ({placeholders})",
            alert_ids,
        ).fetchall()
        alerts = [dict(row) for row in rows]
        return alerts
    finally:
        conn.close()


def _make_clustered_alerts(alerts: list[dict]) -> list[dict]:
    """将原始告警转为聚簇格式（简化版，用于 agent_loop 输入）"""
    if not alerts:
        return []

    clusters: dict[str, list[dict]] = {}
    for alert in alerts:
        title = alert.get("title", "unknown")
        clusters.setdefault(title, []).append(alert)

    result = []
    for title, group in clusters.items():
        sample = group[0]
        result.append({
            "signature": title,
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
    except Exception as exc:
        logger.exception("分析任务异常: trace_id=%s", trace_id)
        _running_tasks[trace_id]["status"] = "error"
        _running_tasks[trace_id]["error"] = str(exc)


def _persist_analysis_result(trace_id: str, alert_ids: list[int], result: dict) -> None:
    """将 Agent 分析结果写回业务表，便于前端统一查询。"""
    conn = _get_db_connection()
    try:
        chain_name = None
        attack_chain = result.get("attack_chain") or []
        if attack_chain and isinstance(attack_chain, list):
            first_stage = attack_chain[0] if isinstance(attack_chain[0], dict) else {}
            chain_name = first_stage.get("stage")

        conn.execute(
            """
            INSERT INTO attack_chains (name, stage, confidence, alert_ids, evidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chain_name or result.get("risk_level") or "Unknown Chain",
                chain_name or "unknown",
                float(result.get("confidence") or 0),
                json.dumps(alert_ids, ensure_ascii=False),
                result.get("rationale") or "",
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
                result.get("risk_level") or "medium",
                result.get("recommendation") or "",
                result.get("action_type") or "investigate",
                result.get("rationale") or "",
            ),
        )

        conn.executemany(
            "UPDATE alerts SET status = ? WHERE id = ?",
            [("analyzing", alert_id) for alert_id in alert_ids],
        )
        conn.commit()
    finally:
        conn.close()


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

    loop = asyncio.get_event_loop()
    task = loop.create_task(_run_analysis(trace_id, clustered, request.model))

    _running_tasks[trace_id] = {
        "task": task,
        "status": "started",
        "result": None,
        "error": None,
        "started_at": datetime.now().isoformat(),
        "alert_ids": request.alert_ids,
    }

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
        client = OpenAI(
            api_key=os.environ.get("XAI_API_KEY"),
            base_url=DEFAULT_BASE_URL,
        )

        messages = [
            {"role": "system", "content": "你是一个工控安全分析助手。"},
        ] + [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        response = client.chat.completions.create(
            model=request.model,
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


@app.post("/approval/{approval_id}/respond")
async def respond_approval(approval_id: int, response: ApprovalResponse):
    """审批响应 — 批准或拒绝工具调用"""
    conn = _get_db_connection()
    try:
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

    finally:
        conn.close()
