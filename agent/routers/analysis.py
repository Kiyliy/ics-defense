"""
Analysis router — agent status, alert analysis, chat, attack chains, decisions.

Migrated from Express backend/src/routes/analysis.js
Existing /analyze and /chat endpoints from service.py are preserved in service.py;
this router adds the Express-facing /api/analysis/* endpoints.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agent.routers._db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

AGENT_SERVICE_URL = os.environ.get("AGENT_SERVICE_URL", "http://localhost:8002")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _get_config(conn, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def _get_config_int(conn, key: str, default: int = 0) -> int:
    raw = _get_config(conn, key)
    if not raw:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AnalysisAlertRequest(BaseModel):
    alert_ids: list[int] = Field(..., min_length=1)


class ChatMessageItem(BaseModel):
    role: str
    content: str


class AnalysisChatRequest(BaseModel):
    messages: list[ChatMessageItem]


class DecisionFeedbackRequest(BaseModel):
    status: str = Field(..., pattern=r"^(accepted|rejected)$")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/agent/status")
async def agent_status(request: Request):
    """Proxy agent status — returns status from the local FastAPI service."""
    # Since we ARE the agent service now, just call the status logic directly
    from agent.service import _mcp_client, _running_tasks

    mcp_connected = _mcp_client is not None
    mcp_servers = _mcp_client.get_connected_servers() if _mcp_client else []
    active_tasks = sum(1 for t in _running_tasks.values() if t["status"] in ("started", "running"))

    return {
        "status": "ok",
        "mcp_connected": mcp_connected,
        "mcp_servers": mcp_servers,
        "running_tasks": active_tasks,
    }


@router.get("/mcp/servers")
async def mcp_servers_proxy():
    """Proxy MCP servers info — returns MCP server data directly."""
    from agent.service import mcp_servers as _mcp_servers_handler
    return await _mcp_servers_handler()


@router.post("/alerts")
async def analyze_alerts(body: AnalysisAlertRequest):
    """Trigger alert analysis via the agent service."""
    alert_ids = body.alert_ids

    if not all(isinstance(aid, int) and aid > 0 for aid in alert_ids):
        raise HTTPException(status_code=400, detail="alert_ids must contain positive integers")

    conn = get_db()
    try:
        placeholders = ",".join("?" for _ in alert_ids)
        alerts = conn.execute(f"SELECT * FROM alerts WHERE id IN ({placeholders})", alert_ids).fetchall()

        if not alerts:
            raise HTTPException(status_code=404, detail="No alerts found")

        found_ids = {a["id"] for a in alerts}
        missing = [aid for aid in alert_ids if aid not in found_ids]
        if missing:
            raise HTTPException(status_code=404, detail=f"Some alerts were not found: missing_alert_ids={missing}")

        # Call the analyze endpoint directly (we are the agent service)
        from agent.service import AnalyzeRequest, analyze as _analyze
        result = await _analyze(AnalyzeRequest(alert_ids=alert_ids))

        # Update alert statuses to "analyzing"
        for aid in alert_ids:
            conn.execute("UPDATE alerts SET status = ? WHERE id = ?", ("analyzing", aid))
        conn.commit()

        return {
            "trace_id": result.trace_id,
            "status": "analyzing",
            "message": "Analysis delegated to Agent Service",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent Service error")
        raise HTTPException(status_code=503, detail="Agent Service unavailable") from exc


@router.post("/chat")
async def analysis_chat(body: AnalysisChatRequest):
    """AI chat with system context injection."""
    conn = get_db()
    try:
        max_messages = _get_config_int(conn, "chat.max_messages", 50)
        if len(body.messages) > max_messages:
            raise HTTPException(status_code=400, detail=f"messages[] exceeds max length ({max_messages})")

        system_context = _build_system_context(conn)

        # Use the LLM directly (ported from Express chat logic)
        from openai import AsyncOpenAI
        from agent.agent import DEFAULT_MODEL, DEFAULT_BASE_URL

        client = AsyncOpenAI(
            api_key=os.environ.get("XAI_API_KEY"),
            base_url=os.environ.get("XAI_BASE_URL", DEFAULT_BASE_URL),
        )

        chat_system_prompt = (
            "你是一个工控安全领域的 AI 助手，专注于工业控制系统（ICS/SCADA）安全。\n\n"
            "你的职责：\n"
            "1. 回答用户关于工控安全的问题，包括安全告警分析、攻击链推断、防护策略等\n"
            "2. 对一般性问候和闲聊做出友好、自然的回应\n"
            "3. 当用户询问当前安全态势时，基于\"当前系统状态\"中的真实数据进行分析和回答\n"
            "4. 可以引用 MITRE ATT&CK for ICS 框架来解释攻击手法\n\n"
            "回复风格：\n"
            "- 使用自然的对话语言，支持 Markdown 格式\n"
            "- 对一般性对话友好回应，不要强行往安全告警上靠\n"
            "- 对专业问题给出详细、专业的回答\n"
            "- 引用具体数据时注明来源（如\"根据系统数据...\"）\n"
            "- 回复应简洁清晰，避免冗余"
        )

        if system_context:
            chat_system_prompt += f"\n\n--- 当前系统状态 ---\n{system_context}"

        messages = [{"role": "system", "content": chat_system_prompt}]
        messages += [{"role": m.role, "content": m.content} for m in body.messages]

        model = os.environ.get("XAI_MODEL", DEFAULT_MODEL)
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.5,
        )

        reply = response.choices[0].message.content or ""
        return {"reply": reply}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail="Chat service temporarily unavailable") from exc


@router.get("/chains")
async def list_chains():
    """Query attack chain list."""
    conn = get_db()
    raw_chains = conn.execute(
        "SELECT c.* FROM attack_chains c ORDER BY c.created_at DESC LIMIT 50"
    ).fetchall()

    chains = []
    for c in raw_chains:
        c_dict = dict(c)
        try:
            alert_ids = json.loads(c_dict.get("alert_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            alert_ids = []

        alerts = []
        if alert_ids:
            ph = ",".join("?" for _ in alert_ids)
            alerts = [dict(a) for a in conn.execute(
                f"SELECT id, title, severity, src_ip FROM alerts WHERE id IN ({ph})", alert_ids
            ).fetchall()]

        decisions = [dict(d) for d in conn.execute(
            "SELECT * FROM decisions WHERE attack_chain_id = ? ORDER BY created_at DESC, id DESC",
            (c_dict["id"],),
        ).fetchall()]

        alert_count = len(alert_ids)
        pending_decisions = [d for d in decisions if d.get("status") == "pending"]
        status = "new" if not decisions else ("pending" if pending_decisions else "resolved")

        primary = decisions[0] if decisions else None
        risk_level = (primary or {}).get("risk_level") or c_dict.get("risk_level", "medium")
        recommendation = (primary or {}).get("recommendation")
        action_type = (primary or {}).get("action_type")
        decision_status = (primary or {}).get("status")

        for d in decisions:
            d["action"] = d.get("recommendation")

        chains.append({
            **c_dict,
            "alerts": alerts,
            "decisions": decisions,
            "alert_count": alert_count,
            "status": status,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "action_type": action_type,
            "decision_status": decision_status,
        })

    return {"chains": chains}


@router.patch("/decisions/{decision_id}")
async def decision_feedback(decision_id: int, body: DecisionFeedbackRequest):
    """Human feedback: accept or reject a decision."""
    status = body.status

    conn = get_db()
    # Atomic update: only succeeds if decision is still pending
    cursor = conn.execute(
        "UPDATE decisions SET status = ? WHERE id = ? AND status = ?",
        (status, decision_id, "pending"),
    )
    if cursor.rowcount == 0:
        existing = conn.execute("SELECT id, status FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Decision not found")
        raise HTTPException(
            status_code=400,
            detail=f"Decision already processed (status: {existing['status']})",
        )

    # Update related alert statuses
    try:
        decision = conn.execute(
            "SELECT attack_chain_id FROM decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        if decision:
            chain = conn.execute(
                "SELECT alert_ids FROM attack_chains WHERE id = ?", (decision["attack_chain_id"],)
            ).fetchone()
            if chain and chain["alert_ids"]:
                try:
                    alert_ids = json.loads(chain["alert_ids"])
                    new_alert_status = "resolved" if status == "accepted" else "analyzed"
                    for aid in alert_ids:
                        conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (new_alert_status, aid))
                except (json.JSONDecodeError, TypeError):
                    pass

        # Write audit log
        conn.execute(
            "INSERT INTO audit_logs (trace_id, alert_id, event_type, data) VALUES (?, ?, ?, ?)",
            (f"decision-{decision_id}", "", "decision_feedback",
             json.dumps({"decision_id": decision_id, "status": status})),
        )
    except Exception:
        logger.exception("Failed to update related alerts")

    conn.commit()
    return {"updated": True}


# ---------------------------------------------------------------------------
# System context builder (ported from Express)
# ---------------------------------------------------------------------------

def _build_system_context(conn) -> str:
    try:
        parts: list[str] = []

        stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'analyzing' THEN 1 ELSE 0 END) as analyzing_count,
                SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical_count,
                SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high_count,
                SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END) as medium_count,
                SUM(CASE WHEN severity = 'low' THEN 1 ELSE 0 END) as low_count
            FROM alerts
        """).fetchone()

        if stats and stats["total"] > 0:
            parts.append(f"告警概览: 共{stats['total']}条告警, 待处理{stats['open_count']}条, 分析中{stats['analyzing_count']}条")
            parts.append(f"严重度分布: 严重{stats['critical_count']} / 高{stats['high_count']} / 中{stats['medium_count']} / 低{stats['low_count']}")
        else:
            parts.append("告警概览: 当前系统无告警记录")

        recent = conn.execute(
            "SELECT id, title, severity, source, src_ip, dst_ip, status, created_at FROM alerts ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        if recent:
            parts.append("\n最近告警:")
            for a in recent:
                parts.append(
                    f"  - [{a['severity']}] {a['title']} (来源:{a['source']}, "
                    f"{a['src_ip'] or '?'}->{a['dst_ip'] or '?'}, 状态:{a['status']})"
                )

        chains = conn.execute(
            "SELECT id, name, stage, confidence FROM attack_chains ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
        if chains:
            parts.append("\n最近攻击链:")
            for c in chains:
                parts.append(f"  - {c['name']} (阶段:{c['stage']}, 置信度:{c['confidence']})")

        asset_count = conn.execute("SELECT COUNT(*) as cnt FROM assets").fetchone()
        if asset_count and asset_count["cnt"] > 0:
            parts.append(f"\n资产: 共{asset_count['cnt']}台受监控资产")

        return "\n".join(parts)
    except Exception:
        logger.exception("Failed to build system context")
        return ""
