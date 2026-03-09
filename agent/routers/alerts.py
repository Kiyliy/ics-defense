"""
Alerts router — POST /ingest, GET /, GET /:id, PATCH /:id/status

Migrated from Express backend/src/routes/alerts.js
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field

from agent.routers._db import get_db
from collector.normalizer import normalize as _normalize_raw

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Normalizer bridge — delegates to collector.normalizer and returns a dict
# ---------------------------------------------------------------------------

def normalize(source: str, raw_event: Any) -> dict:
    """Normalize a raw event dict via the canonical collector normalizer.

    Returns a plain dict with the keys expected by the alerts table.
    """
    event = raw_event if isinstance(raw_event, dict) else {}
    normalized_alert = _normalize_raw(source, event)
    d = normalized_alert.to_dict()
    # Drop fields not needed for DB insertion (keep the subset used by ingest)
    return {
        "source": d.get("source"),
        "severity": d.get("severity"),
        "title": d.get("title"),
        "description": d.get("description"),
        "src_ip": d.get("src_ip"),
        "dst_ip": d.get("dst_ip"),
        "mitre_tactic": d.get("mitre_tactic"),
        "mitre_technique": d.get("mitre_technique"),
    }


# ---------------------------------------------------------------------------
# Config helpers (from shared _helpers module)
# ---------------------------------------------------------------------------

from agent.routers._helpers import get_config as _get_config, get_config_int as _get_config_int


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    source: str
    events: list[dict[str, Any]]


class IngestResponse(BaseModel):
    ingested: int
    alerts: list[dict[str, Any]]


class AlertListResponse(BaseModel):
    total: int
    alerts: list[dict[str, Any]]


class StatusUpdateRequest(BaseModel):
    status: str


VALID_TRANSITIONS: dict[str, list[str]] = {
    "open": ["analyzing"],
    "analyzing": ["analyzed", "open"],
    "analyzed": ["resolved", "open"],
    "resolved": ["open"],
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=IngestResponse)
async def ingest_events(request: IngestRequest):
    """Multi-source event ingestion: normalize raw events and store as alerts."""
    conn = get_db()
    try:
        source = request.source
        events = request.events

        valid_sources_str = _get_config(conn, "ingest.valid_sources", "waf,nids,hids,pikachu,soc")
        valid_sources = [s.strip() for s in valid_sources_str.split(",")]
        max_batch = _get_config_int(conn, "ingest.max_batch_size", 1000)

        if source not in valid_sources:
            raise HTTPException(status_code=400, detail=f"source must be one of: {', '.join(valid_sources)}")
        if len(events) == 0:
            raise HTTPException(status_code=400, detail="events[] must not be empty")
        if len(events) > max_batch:
            raise HTTPException(status_code=400, detail=f"events[] exceeds max batch size ({max_batch})")

        clustering_window = _get_config_int(conn, "ingest.clustering_window_hours", 1)
        results: list[dict[str, Any]] = []

        for event in events:
            # Insert raw event
            cursor = conn.execute(
                "INSERT INTO raw_events (source, raw_json) VALUES (?, ?)",
                (source, json.dumps(event)),
            )
            raw_event_id = cursor.lastrowid

            normalized = normalize(source, event)
            normalized["raw_event_id"] = raw_event_id

            # Clustering: merge if same source + title + severity within window
            existing = conn.execute(
                """
                SELECT id FROM alerts
                WHERE source = ? AND title = ? AND severity = ?
                  AND created_at >= datetime('now', '-' || ? || ' hours')
                ORDER BY created_at DESC LIMIT 1
                """,
                (normalized["source"], normalized["title"], normalized["severity"], str(clustering_window)),
            ).fetchone()

            if existing:
                conn.execute("UPDATE alerts SET event_count = event_count + 1 WHERE id = ?", (existing["id"],))
                results.append({"id": existing["id"], "clustered": True, **normalized})
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO alerts (source, severity, title, description, src_ip, dst_ip,
                                        mitre_tactic, mitre_technique, raw_event_id, event_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        normalized["source"], normalized["severity"], normalized["title"],
                        normalized["description"], normalized.get("src_ip"), normalized.get("dst_ip"),
                        normalized.get("mitre_tactic"), normalized.get("mitre_technique"),
                        raw_event_id,
                    ),
                )
                results.append({"id": cursor.lastrowid, **normalized})

        conn.commit()
        return IngestResponse(ingested=len(results), alerts=results)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Ingest batch failed")
        raise HTTPException(status_code=500, detail="Failed to ingest events") from exc


@router.get("/", response_model=AlertListResponse)
async def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(default=50, ge=0),
    offset: int = Query(default=0, ge=0),
):
    """Query alerts list with filtering and pagination."""
    conn = get_db()
    where_parts: list[str] = []
    params: dict[str, Any] = {}
    if status:
        where_parts.append("status = :status")
        params["status"] = status
    if severity:
        where_parts.append("severity = :severity")
        params["severity"] = severity
    if source:
        where_parts.append("source = :source")
        params["source"] = source

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    params["limit"] = limit
    params["offset"] = offset

    alerts = conn.execute(
        f"SELECT * FROM alerts {where_clause} ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
        params,
    ).fetchall()

    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total_row = conn.execute(
        f"SELECT COUNT(*) as count FROM alerts {where_clause}", count_params
    ).fetchone()

    return AlertListResponse(
        total=total_row["count"],
        alerts=[dict(a) for a in alerts],
    )


@router.get("/{alert_id}")
async def get_alert(alert_id: int = Path(...)):
    """Query single alert details."""
    conn = get_db()
    alert = conn.execute(
        """SELECT a.*, r.raw_json, r.source as raw_source
           FROM alerts a LEFT JOIN raw_events r ON a.raw_event_id = r.id
           WHERE a.id = ?""",
        (alert_id,),
    ).fetchone()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    result = dict(alert)
    if result.get("raw_json"):
        try:
            result["raw_json"] = json.loads(result["raw_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return result


@router.patch("/{alert_id}/status")
async def update_alert_status(alert_id: int, body: StatusUpdateRequest):
    """Update alert status with state transition validation."""
    status = body.status
    if status not in ("open", "analyzing", "analyzed", "resolved"):
        raise HTTPException(status_code=400, detail="Invalid status")

    conn = get_db()
    current = conn.execute("SELECT id, status FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    if not current:
        raise HTTPException(status_code=404, detail="Alert not found")

    allowed = VALID_TRANSITIONS.get(current["status"], [])
    if status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current['status']} -> {status}. Allowed: {', '.join(allowed) or 'none'}",
        )

    conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (status, alert_id))

    import time
    conn.execute(
        "INSERT INTO audit_logs (trace_id, alert_id, event_type, data) VALUES (?, ?, ?, ?)",
        (f"manual-{int(time.time() * 1000)}", str(alert_id), "alert_status_change",
         json.dumps({"from": current["status"], "to": status})),
    )
    conn.commit()
    return {"updated": True}
