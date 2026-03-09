"""
Notifications router — channels CRUD, rules CRUD, history, providers, test, send.

Provides the full notification management API consumed by the frontend
components (ChannelConfig.vue, NotifyRules.vue, NotifyHistory.vue).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from agent.routers._db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Simplified notification service (no Redis dependency)
# ---------------------------------------------------------------------------

def _list_providers() -> list[dict[str, Any]]:
    """List available notification providers."""
    feishu_webhook = os.environ.get("FEISHU_BOT_WEBHOOK_URL", "")
    feishu_app_id = os.environ.get("FEISHU_APP_ID", "")

    providers = [
        {"name": "noop", "enabled": True, "is_default": False},
        {"name": "feishu", "enabled": bool(feishu_webhook), "is_default": False},
        {"name": "feishu-app", "enabled": bool(feishu_app_id), "is_default": False},
    ]

    # Determine default
    default_provider = os.environ.get("NOTIFICATION_PROVIDER", "")
    if not default_provider:
        if feishu_app_id:
            default_provider = "feishu-app"
        elif feishu_webhook:
            default_provider = "feishu"
        else:
            default_provider = "noop"

    for p in providers:
        p["is_default"] = p["name"] == default_provider

    return providers


def _build_alert_notification(alert: dict) -> dict:
    """Build notification payload from alert data."""
    body_parts = [
        f"来源：{alert.get('source', '')}",
        f"等级：{alert.get('severity', '')}",
        f"状态：{alert.get('status', '')}",
    ]
    if alert.get("src_ip"):
        body_parts.append(f"源IP：{alert['src_ip']}")
    if alert.get("dst_ip"):
        body_parts.append(f"目标IP：{alert['dst_ip']}")
    if alert.get("mitre_tactic"):
        body_parts.append(f"战术：{alert['mitre_tactic']}")
    if alert.get("mitre_technique"):
        body_parts.append(f"技术：{alert['mitre_technique']}")
    if alert.get("description"):
        body_parts.append(f"描述：{alert['description']}")
    body_parts.append(f"告警ID：{alert.get('id', '')}")

    return {
        "title": f"告警通知：{alert.get('title', '')}",
        "body": "\n".join(body_parts),
        "msg_type": "post",
        "metadata": {"alert_id": alert.get("id")},
    }


def _validate_provider(provider: str | None) -> str:
    """Validate and resolve provider name."""
    valid = {"noop", "feishu", "feishu-app"}
    providers = _list_providers()
    default_name = next((p["name"] for p in providers if p["is_default"]), "noop")

    name = provider or default_name
    if name not in valid:
        raise HTTPException(status_code=400, detail=f"Unsupported notification provider: {name}")

    # Check if provider is configured
    provider_info = next((p for p in providers if p["name"] == name), None)
    if provider_info and name != "noop" and not provider_info["enabled"]:
        raise HTTPException(status_code=400, detail=f"Notification provider not configured: {name}")

    if name == "feishu-app" and not os.environ.get("FEISHU_APP_RECEIVE_ID"):
        # Will need receive_id from the request
        pass

    return name


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TestNotificationRequest(BaseModel):
    provider: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    text: Optional[str] = None
    msg_type: Optional[str] = None
    card: Optional[dict] = None
    receive_id: Optional[str] = None
    receive_id_type: Optional[str] = None


class SendAlertNotificationRequest(BaseModel):
    provider: Optional[str] = None
    receive_id: Optional[str] = None
    receive_id_type: Optional[str] = None


class ChannelCreateRequest(BaseModel):
    id: Optional[int] = None
    type: str
    webhook: str


class RuleSaveRequest(BaseModel):
    id: Optional[int] = None
    event: Optional[str] = None
    channel: Optional[str] = None
    enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Routes — Providers / Test / Send
# ---------------------------------------------------------------------------

@router.get("/providers")
async def list_notification_providers():
    """List available notification providers."""
    return {"providers": _list_providers()}


@router.post("/test", status_code=202)
async def test_notification(body: TestNotificationRequest):
    """Send a test notification."""
    if not body.text and not body.body and not body.title and not body.card:
        raise HTTPException(status_code=400, detail="text, body, title or card is required")

    try:
        provider_name = _validate_provider(body.provider)

        if provider_name == "feishu-app" and not body.receive_id and not os.environ.get("FEISHU_APP_RECEIVE_ID"):
            raise HTTPException(
                status_code=400,
                detail="receive_id is required for feishu-app notifications",
            )

        # In production, this would enqueue to Redis. For now, log and return success.
        logger.info("Test notification queued: provider=%s title=%s", provider_name, body.title)
        return {"queued": True, "provider": provider_name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Notification service error")
        raise HTTPException(status_code=500, detail="Notification service error") from exc


@router.post("/alerts/{alert_id}/send", status_code=202)
async def send_alert_notification(alert_id: int, body: SendAlertNotificationRequest):
    """Send notification for a specific alert."""
    conn = get_db()
    try:
        alert = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert_dict = dict(alert)
        notification = _build_alert_notification(alert_dict)

        provider_name = _validate_provider(body.provider)

        if provider_name == "feishu-app" and not body.receive_id and not os.environ.get("FEISHU_APP_RECEIVE_ID"):
            raise HTTPException(
                status_code=400,
                detail="receive_id is required for feishu-app notifications",
            )

        # Record in notification history
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO notification_history (event, channel, status, time) VALUES (?, ?, ?, ?)",
            (notification["title"], provider_name, "success", now),
        )
        conn.commit()

        logger.info("Alert notification queued: alert_id=%d provider=%s", alert_id, provider_name)
        return {"alert_id": alert_id, "queued": True, "provider": provider_name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Notification service error")
        raise HTTPException(status_code=500, detail="Notification service error") from exc


# ---------------------------------------------------------------------------
# Routes — Channels CRUD
# ---------------------------------------------------------------------------

@router.get("/channels")
async def list_channels():
    """List all configured notification channels."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, type, webhook, created_at FROM notification_channels ORDER BY id"
    ).fetchall()
    return {"channels": [dict(r) for r in rows]}


@router.post("/channels")
async def create_or_update_channel(body: ChannelCreateRequest):
    """Create or update a notification channel."""
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if body.id is not None:
        # Update existing channel
        existing = conn.execute(
            "SELECT id FROM notification_channels WHERE id = ?", (body.id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Channel not found")
        conn.execute(
            "UPDATE notification_channels SET type = ?, webhook = ? WHERE id = ?",
            (body.type, body.webhook, body.id),
        )
        conn.commit()
        return {"id": body.id, "type": body.type, "webhook": body.webhook}
    else:
        # Create new channel
        cursor = conn.execute(
            "INSERT INTO notification_channels (type, webhook, created_at) VALUES (?, ?, ?)",
            (body.type, body.webhook, now),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "type": body.type, "webhook": body.webhook}


@router.post("/channels/{channel_id}/test")
async def test_channel(channel_id: int):
    """Send a test notification through a specific channel."""
    conn = get_db()
    channel = conn.execute(
        "SELECT * FROM notification_channels WHERE id = ?", (channel_id,)
    ).fetchone()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    ch = dict(channel)
    # In production, this would actually send a test message to the webhook.
    # For now, log it and record in history.
    logger.info("Test notification sent to channel %d (%s): %s", channel_id, ch["type"], ch["webhook"])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO notification_history (event, channel, status, time) VALUES (?, ?, ?, ?)",
        (f"测试通知 - {ch['type']}", ch["type"], "success", now),
    )
    conn.commit()

    return {"success": True}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int):
    """Delete a notification channel."""
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM notification_channels WHERE id = ?", (channel_id,)
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Channel not found")

    conn.execute("DELETE FROM notification_channels WHERE id = ?", (channel_id,))
    conn.commit()
    return {"deleted": True, "id": channel_id}


# ---------------------------------------------------------------------------
# Routes — Notification Rules
# ---------------------------------------------------------------------------

_DEFAULT_RULES = [
    {"event": "新告警", "channel": "飞书", "enabled": True},
    {"event": "高危告警", "channel": "飞书", "enabled": True},
    {"event": "攻击链发现", "channel": "飞书", "enabled": False},
    {"event": "审批请求", "channel": "飞书", "enabled": False},
]


def _ensure_default_rules(conn) -> None:
    """Seed default notification rules if the table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM notification_rules").fetchone()[0]
    if count == 0:
        for rule in _DEFAULT_RULES:
            conn.execute(
                "INSERT INTO notification_rules (event, channel, enabled) VALUES (?, ?, ?)",
                (rule["event"], rule["channel"], 1 if rule["enabled"] else 0),
            )
        conn.commit()


@router.get("/rules")
async def list_rules():
    """List all notification rules."""
    conn = get_db()
    _ensure_default_rules(conn)
    rows = conn.execute(
        "SELECT id, event, channel, enabled FROM notification_rules ORDER BY id"
    ).fetchall()
    rules = []
    for r in rows:
        d = dict(r)
        d["enabled"] = bool(d["enabled"])
        rules.append(d)
    return {"rules": rules}


@router.put("/rules")
async def save_rule(body: RuleSaveRequest):
    """Update a notification rule (typically toggling enabled)."""
    conn = get_db()

    if body.id is not None:
        existing = conn.execute(
            "SELECT id FROM notification_rules WHERE id = ?", (body.id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Rule not found")

        updates = []
        params = []
        if body.event is not None:
            updates.append("event = ?")
            params.append(body.event)
        if body.channel is not None:
            updates.append("channel = ?")
            params.append(body.channel)
        if body.enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if body.enabled else 0)

        if updates:
            params.append(body.id)
            conn.execute(
                f"UPDATE notification_rules SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        row = conn.execute(
            "SELECT id, event, channel, enabled FROM notification_rules WHERE id = ?",
            (body.id,),
        ).fetchone()
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        return d
    else:
        # Create new rule
        if not body.event or not body.channel:
            raise HTTPException(status_code=400, detail="event and channel are required for new rules")
        cursor = conn.execute(
            "INSERT INTO notification_rules (event, channel, enabled) VALUES (?, ?, ?)",
            (body.event, body.channel, 1 if body.enabled else 0),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "event": body.event, "channel": body.channel, "enabled": bool(body.enabled)}


# ---------------------------------------------------------------------------
# Routes — Notification History
# ---------------------------------------------------------------------------

@router.get("/history")
async def list_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Fetch notification send history with pagination."""
    conn = get_db()

    total_row = conn.execute("SELECT COUNT(*) FROM notification_history").fetchone()
    total = total_row[0] if total_row else 0

    rows = conn.execute(
        "SELECT id, event, channel, status, time, created_at "
        "FROM notification_history ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()

    return {"history": [dict(r) for r in rows], "total": total}
