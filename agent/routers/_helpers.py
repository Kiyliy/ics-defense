"""
Shared helper functions for routers.

Consolidates duplicated utilities (e.g. config readers) that were previously
defined inline in multiple router modules.
"""

from __future__ import annotations

import sqlite3


def get_config(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    """Read a value from the system_config table."""
    row = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_config_int(conn: sqlite3.Connection, key: str, default: int = 0) -> int:
    """Read an integer value from the system_config table."""
    raw = get_config(conn, key)
    if not raw:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default
