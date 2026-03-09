"""
Approval router — GET /, GET /:id, PATCH /:id

Migrated from Express backend/src/routes/approval.js
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from agent.routers._db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approval", tags=["approval"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ApprovalPatchRequest(BaseModel):
    status: str = Field(..., pattern=r"^(approved|rejected)$")
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def list_approvals(status: Optional[str] = None):
    """Query approval list, optionally filter by ?status=pending."""
    conn = get_db()
    where_parts: list[str] = []
    params: dict[str, str] = {}
    if status:
        where_parts.append("status = :status")
        params["status"] = status

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    approvals = conn.execute(
        f"SELECT * FROM approval_queue {where_clause} ORDER BY created_at DESC", params
    ).fetchall()
    total_row = conn.execute(
        f"SELECT COUNT(*) as count FROM approval_queue {where_clause}", params
    ).fetchone()

    return {
        "approvals": [dict(a) for a in approvals],
        "total": total_row["count"],
    }


@router.get("/{approval_id}")
async def get_approval(approval_id: int = Path(...)):
    """Query single approval details."""
    conn = get_db()
    approval = conn.execute(
        "SELECT * FROM approval_queue WHERE id = ?", (approval_id,)
    ).fetchone()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return dict(approval)


@router.patch("/{approval_id}")
async def patch_approval(approval_id: int, body: ApprovalPatchRequest):
    """Approve or reject an approval item."""
    conn = get_db()
    now = datetime.now().isoformat()

    # Atomic update: only succeeds if current status is 'pending'
    cursor = conn.execute(
        "UPDATE approval_queue SET status = ?, reason = COALESCE(?, reason), responded_at = ? WHERE id = ? AND status = ?",
        (body.status, body.reason, now, approval_id, "pending"),
    )

    if cursor.rowcount == 0:
        existing = conn.execute(
            "SELECT id, status FROM approval_queue WHERE id = ?", (approval_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Approval not found")
        raise HTTPException(
            status_code=400,
            detail=f"Approval already processed (status: {existing['status']})",
        )

    # Write audit log
    conn.execute(
        "INSERT INTO audit_logs (trace_id, alert_id, event_type, data) VALUES (?, ?, ?, ?)",
        (
            f"approval-{approval_id}",
            "",
            "approval_decision",
            json.dumps({"approval_id": approval_id, "status": body.status, "reason": body.reason}),
        ),
    )
    conn.commit()

    updated = conn.execute(
        "SELECT * FROM approval_queue WHERE id = ?", (approval_id,)
    ).fetchone()
    return dict(updated)
