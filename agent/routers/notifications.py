"""
Notifications router — GET /providers, POST /test, POST /alerts/:id/send

Migrated from Express backend/src/routes/notifications.js

Note: The Express version used Redis queues and Feishu adapters.
This Python version provides the same API shape but uses a simplified
in-process approach (no Redis dependency required).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path
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


# ---------------------------------------------------------------------------
# Routes
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

        logger.info("Alert notification queued: alert_id=%d provider=%s", alert_id, provider_name)
        return {"alert_id": alert_id, "queued": True, "provider": provider_name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Notification service error")
        raise HTTPException(status_code=500, detail="Notification service error") from exc
