"""
Audit router — GET /, GET /stats, GET /trace/:trace_id

Migrated from Express backend/src/routes/audit.js
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Path

from agent.routers._db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_token_usage(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _build_since_iso(days: int) -> str:
    since = datetime.now() - timedelta(days=days)
    return since.isoformat()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def list_audit_logs(
    trace_id: Optional[str] = None,
    alert_id: Optional[str] = None,
    days: int = Query(default=7, gt=0),
    limit: int = Query(default=50, ge=0),
    offset: int = Query(default=0, ge=0),
):
    """Query audit logs with filtering and pagination."""
    conn = get_db()
    where_parts: list[str] = []
    params: dict[str, Any] = {}

    if trace_id:
        where_parts.append("trace_id = :trace_id")
        params["trace_id"] = trace_id
    if alert_id:
        where_parts.append("alert_id = :alert_id")
        params["alert_id"] = alert_id

    where_parts.append("created_at >= :since")
    params["since"] = _build_since_iso(days)
    params["limit"] = limit
    params["offset"] = offset

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    logs = conn.execute(
        f"SELECT * FROM audit_logs {where_clause} ORDER BY created_at ASC LIMIT :limit OFFSET :offset",
        params,
    ).fetchall()

    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total_row = conn.execute(
        f"SELECT COUNT(*) as count FROM audit_logs {where_clause}", count_params
    ).fetchone()

    return {"logs": [dict(l) for l in logs], "total": total_row["count"]}


@router.get("/stats")
async def audit_stats(days: int = Query(default=7, gt=0)):
    """Token usage statistics."""
    conn = get_db()
    since_str = _build_since_iso(days)

    total_analyses = conn.execute(
        "SELECT COUNT(DISTINCT trace_id) as count FROM audit_logs WHERE created_at >= ?",
        (since_str,),
    ).fetchone()

    token_rows = conn.execute(
        "SELECT token_usage, DATE(created_at) as date FROM audit_logs WHERE token_usage IS NOT NULL AND created_at >= ?",
        (since_str,),
    ).fetchall()

    total_input = 0
    total_output = 0
    daily_map: dict[str, dict[str, Any]] = {}

    for row in token_rows:
        usage = _parse_token_usage(row["token_usage"])
        if not usage:
            continue
        inp = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        total_input += inp
        total_output += out

        date = row["date"]
        if date not in daily_map:
            daily_map[date] = {"date": date, "analyses": 0, "tokens": 0}
        daily_map[date]["tokens"] += inp + out

    daily_analyses = conn.execute(
        "SELECT DATE(created_at) as date, COUNT(DISTINCT trace_id) as analyses FROM audit_logs WHERE created_at >= ? GROUP BY DATE(created_at)",
        (since_str,),
    ).fetchall()

    for row in daily_analyses:
        date = row["date"]
        if date not in daily_map:
            daily_map[date] = {"date": date, "analyses": 0, "tokens": 0}
        daily_map[date]["analyses"] = row["analyses"]

    daily = sorted(daily_map.values(), key=lambda x: x["date"])

    return {
        "total_analyses": total_analyses["count"],
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "daily": daily,
    }


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str = Path(...)):
    """Query complete reasoning chain for a trace."""
    conn = get_db()
    logs = conn.execute(
        "SELECT * FROM audit_logs WHERE trace_id = ? ORDER BY created_at ASC",
        (trace_id,),
    ).fetchall()

    if not logs:
        raise HTTPException(status_code=404, detail="Trace not found")

    total_tokens = 0
    log_list = []
    for log in logs:
        d = dict(log)
        log_list.append(d)
        usage = _parse_token_usage(d.get("token_usage"))
        if usage:
            total_tokens += (usage.get("input_tokens") or usage.get("prompt_tokens") or 0) + \
                            (usage.get("output_tokens") or usage.get("completion_tokens") or 0)

    return {
        "trace_id": trace_id,
        "logs": log_list,
        "summary": {
            "total_steps": len(log_list),
            "total_tokens": total_tokens,
        },
    }
