"""
Config router — GET /, GET /:key, PUT /:key, PUT /, POST /reload

Migrated from Express backend/src/routes/config.js
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Request

from agent.routers._db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def get_all_config():
    """Return all system configuration."""
    conn = get_db()
    configs = [dict(r) for r in conn.execute(
        "SELECT key, value, description, updated_at FROM system_config ORDER BY key"
    ).fetchall()]
    return {"configs": configs}


@router.get("/{key:path}")
async def get_config_by_key(key: str = Path(...)):
    """Query a single config item."""
    conn = get_db()
    configs = [dict(r) for r in conn.execute(
        "SELECT key, value, description, updated_at FROM system_config ORDER BY key"
    ).fetchall()]
    item = next((c for c in configs if c["key"] == key), None)
    if not item:
        raise HTTPException(status_code=404, detail=f'Config key "{key}" not found')
    return item


@router.put("/{key:path}")
async def update_config_by_key(key: str, request: Request):
    """Update a single config item."""
    body = await request.json()
    value = body.get("value")
    if value is None:
        raise HTTPException(status_code=400, detail="value is required")

    conn = get_db()
    conn.execute(
        """INSERT INTO system_config (key, value, updated_at) VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
        (key, str(value)),
    )
    conn.commit()
    return {"key": key, "value": str(value), "updated": True}


@router.put("/")
async def batch_update_config(request: Request):
    """Batch update configuration."""
    entries = await request.json()
    if not isinstance(entries, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object of { key: value } pairs")

    conn = get_db()
    updated: list[str] = []
    for key, value in entries.items():
        conn.execute(
            """INSERT INTO system_config (key, value, updated_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, str(value)),
        )
        updated.append(key)
    conn.commit()
    return {"updated": updated}


@router.post("/reload")
async def reload_config():
    """Reload config cache (no-op in Python version — reads directly from DB)."""
    return {"reloaded": True}
