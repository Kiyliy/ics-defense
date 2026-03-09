"""
Dashboard router — GET /stats, GET /trend, GET /assets, POST /assets

Migrated from Express backend/src/routes/dashboard.js
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent.routers._db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateAssetRequest(BaseModel):
    ip: str
    hostname: Optional[str] = None
    type: str = "host"
    importance: int = 3


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats")
async def dashboard_stats():
    """Dashboard summary statistics."""
    conn = get_db()
    alerts_by_status = [dict(r) for r in conn.execute(
        "SELECT status, COUNT(*) as count FROM alerts GROUP BY status"
    ).fetchall()]

    alerts_by_severity = [dict(r) for r in conn.execute(
        "SELECT severity, COUNT(*) as count FROM alerts GROUP BY severity"
    ).fetchall()]

    alerts_by_source = [dict(r) for r in conn.execute(
        "SELECT source, COUNT(*) as count FROM alerts GROUP BY source"
    ).fetchall()]

    recent_alerts = [dict(r) for r in conn.execute(
        "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 10"
    ).fetchall()]

    active_chains = [dict(r) for r in conn.execute("""
        SELECT c.*, d.risk_level, d.recommendation, d.action_type, d.status as decision_status
        FROM attack_chains c
        LEFT JOIN decisions d ON d.attack_chain_id = c.id
        ORDER BY c.created_at DESC LIMIT 5
    """).fetchall()]

    total_alerts = conn.execute("SELECT COUNT(*) as count FROM alerts").fetchone()
    total_chains = conn.execute("SELECT COUNT(*) as count FROM attack_chains").fetchone()
    pending_decisions = conn.execute(
        "SELECT COUNT(*) as count FROM decisions WHERE status = 'pending'"
    ).fetchone()

    return {
        "summary": {
            "totalAlerts": total_alerts["count"],
            "totalChains": total_chains["count"],
            "pendingDecisions": pending_decisions["count"],
        },
        "alertsByStatus": alerts_by_status,
        "alertsBySeverity": alerts_by_severity,
        "alertsBySource": alerts_by_source,
        "recentAlerts": recent_alerts,
        "activeChains": active_chains,
    }


@router.get("/trend")
async def dashboard_trend():
    """Alert trend over the last 7 days."""
    conn = get_db()
    trend = [dict(r) for r in conn.execute("""
        SELECT date(created_at) as date, COUNT(*) as count
        FROM alerts
        WHERE created_at >= date('now', '-7 days')
        GROUP BY date(created_at)
        ORDER BY date ASC
    """).fetchall()]
    return {"trend": trend}


@router.get("/assets")
async def list_assets():
    """Asset list with alert counts."""
    conn = get_db()
    assets = [dict(r) for r in conn.execute("""
        SELECT a.*,
            (SELECT COUNT(*) FROM alerts WHERE dst_ip = a.ip) as alert_count
        FROM assets a
        ORDER BY alert_count DESC
    """).fetchall()]
    return {"assets": assets}


@router.post("/assets")
async def create_asset(body: CreateAssetRequest):
    """Add a new asset."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO assets (ip, hostname, type, importance) VALUES (?, ?, ?, ?)",
        (body.ip, body.hostname, body.type, body.importance),
    )
    conn.commit()
    return {"id": cursor.lastrowid}
