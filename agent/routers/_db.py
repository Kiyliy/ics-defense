"""
Shared database helper for routers.

Uses the unified agent.db module for database access.
"""

from __future__ import annotations

import os
import sqlite3

from agent.db import get_db as _get_db_ctx, _local, _get_db_path, _ensure_data_dir

DB_PATH = os.environ.get("DB_PATH", "data/ics_defense.db")


def get_db(db_path: str | None = None) -> sqlite3.Connection:
    """Get a database connection with Row factory.

    Returns a raw ``sqlite3.Connection`` for backward compatibility with
    routers that do ``conn = get_db()``.

    The connection comes from the per-thread pool managed by
    ``agent.db``.  Because the pool keeps the connection alive across
    calls, this is safe — and we no longer abuse ``__enter__`` without a
    matching ``__exit__``.

    Callers that perform writes should call ``conn.commit()`` on success.
    If an exception propagates, the next call to ``agent.db.get_db()``
    (as a context manager) will issue a rollback automatically.
    """
    path = db_path or DB_PATH
    _ensure_data_dir(path)

    # Reuse the per-thread connection, same logic as agent.db.get_db
    conn: sqlite3.Connection | None = getattr(_local, "conn", None)
    conn_path: str | None = getattr(_local, "conn_path", None)

    if conn is None or conn_path != path:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        _local.conn_path = path

    return conn
