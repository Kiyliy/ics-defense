"""
Unified SQLite data layer for ICS Defense Platform.

Single authoritative source for all table definitions, indexes, and DB access.
All Python components should import from this module instead of using sqlite3 directly.

Usage::

    from agent.db import init_db, get_db, query_one, query_all, execute, execute_many

    # At startup
    init_db()

    # In request handlers / business logic
    with get_db() as conn:
        rows = query_all(conn, "SELECT * FROM alerts WHERE severity = ?", ("high",))

    # Or use the convenience helpers (they manage their own connection):
    row = query_one("SELECT * FROM alerts WHERE id = ?", (1,))
    execute("UPDATE alerts SET status = ? WHERE id = ?", ("resolved", 1))
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("DB_PATH", "data/ics_defense.db")

# ---------------------------------------------------------------------------
# Schema: all tables and indexes (authoritative source)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS assets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ip          TEXT NOT NULL,
    hostname    TEXT,
    type        TEXT DEFAULT 'host',
    importance  INTEGER DEFAULT 3,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS raw_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    raw_json    TEXT NOT NULL,
    received_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    severity        TEXT DEFAULT 'medium',
    title           TEXT NOT NULL,
    description     TEXT,
    src_ip          TEXT,
    dst_ip          TEXT,
    src_port        INTEGER,
    dst_port        INTEGER,
    protocol        TEXT,
    raw_json        TEXT,
    mitre_tactic    TEXT,
    mitre_technique TEXT,
    asset_id        INTEGER REFERENCES assets(id),
    status          TEXT DEFAULT 'open',
    raw_event_id    INTEGER REFERENCES raw_events(id),
    event_count     INTEGER DEFAULT 1,
    cluster_signature TEXT,
    cluster_count   INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS attack_chains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT,
    stage       TEXT,
    confidence  REAL DEFAULT 0.0,
    alert_ids   TEXT,
    evidence    TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attack_chain_id INTEGER REFERENCES attack_chains(id),
    risk_level      TEXT DEFAULT 'medium',
    recommendation  TEXT NOT NULL,
    action_type     TEXT,
    rationale       TEXT,
    status          TEXT DEFAULT 'pending',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS approval_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id      TEXT NOT NULL,
    tool_name     TEXT NOT NULL,
    tool_args     TEXT,
    reason        TEXT,
    status        TEXT DEFAULT 'pending',
    responded_at  TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id      TEXT NOT NULL,
    alert_id      TEXT,
    event_type    TEXT NOT NULL,
    data          TEXT,
    token_usage   TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analysis_tasks (
    trace_id     TEXT PRIMARY KEY,
    status       TEXT DEFAULT 'started',
    alert_ids    TEXT,
    result       TEXT,
    error        TEXT,
    started_at   TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS notification_channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,
    webhook     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notification_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event       TEXT NOT NULL,
    channel     TEXT NOT NULL,
    enabled     INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notification_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event       TEXT NOT NULL,
    channel     TEXT NOT NULL,
    status      TEXT DEFAULT 'success',
    time        TEXT DEFAULT (datetime('now')),
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Indexes: alerts
CREATE INDEX IF NOT EXISTS idx_alerts_status     ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity   ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created    ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_asset      ON alerts(asset_id);
CREATE INDEX IF NOT EXISTS idx_alerts_raw_event  ON alerts(raw_event_id);

-- Indexes: decisions
CREATE INDEX IF NOT EXISTS idx_decisions_chain   ON decisions(attack_chain_id);

-- Indexes: approval_queue
CREATE INDEX IF NOT EXISTS idx_approval_status   ON approval_queue(status);

-- Indexes: audit_logs
CREATE INDEX IF NOT EXISTS idx_audit_trace       ON audit_logs(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_alert       ON audit_logs(alert_id);
"""

# ---------------------------------------------------------------------------
# Migration: add columns that may be missing on older databases
# ---------------------------------------------------------------------------

_MIGRATIONS = [
    # (check_sql, migration_sql)
    (
        "SELECT event_count FROM alerts LIMIT 1",
        "ALTER TABLE alerts ADD COLUMN event_count INTEGER DEFAULT 1",
    ),
    (
        "SELECT src_port FROM alerts LIMIT 1",
        "ALTER TABLE alerts ADD COLUMN src_port INTEGER",
    ),
    (
        "SELECT dst_port FROM alerts LIMIT 1",
        "ALTER TABLE alerts ADD COLUMN dst_port INTEGER",
    ),
    (
        "SELECT protocol FROM alerts LIMIT 1",
        "ALTER TABLE alerts ADD COLUMN protocol TEXT",
    ),
    (
        "SELECT raw_json FROM alerts LIMIT 1",
        "ALTER TABLE alerts ADD COLUMN raw_json TEXT",
    ),
    (
        "SELECT cluster_signature FROM alerts LIMIT 1",
        "ALTER TABLE alerts ADD COLUMN cluster_signature TEXT",
    ),
    (
        "SELECT cluster_count FROM alerts LIMIT 1",
        "ALTER TABLE alerts ADD COLUMN cluster_count INTEGER DEFAULT 1",
    ),
    (
        "SELECT updated_at FROM alerts LIMIT 1",
        "ALTER TABLE alerts ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))",
    ),
]

# ---------------------------------------------------------------------------
# Connection pool (per-thread reuse)
# ---------------------------------------------------------------------------

_local = threading.local()


def _get_db_path() -> str:
    """Resolve the database path, respecting runtime overrides."""
    return os.environ.get("DB_PATH", DB_PATH)


def _ensure_data_dir(db_path: str) -> None:
    """Create the parent directory for the database file if it does not exist."""
    parent = Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)


def init_db(db_path: str | None = None) -> None:
    """Initialize the database: create all tables, indexes, and run migrations.

    This is idempotent and safe to call multiple times. It should be invoked
    once at application startup.

    Parameters
    ----------
    db_path : str | None
        Override the default DB path. When ``None``, uses ``DB_PATH``
        (which itself reads from the ``DB_PATH`` environment variable).
    """
    path = db_path or _get_db_path()
    _ensure_data_dir(path)

    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA_SQL)

        # Run migrations
        for check_sql, migration_sql in _MIGRATIONS:
            try:
                conn.execute(check_sql)
            except sqlite3.OperationalError:
                conn.execute(migration_sql)

        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db(db_path: str | None = None):
    """Context manager that yields a ``sqlite3.Connection``.

    Connections are cached per-thread for reuse. The connection uses
    ``Row`` row factory so results can be accessed by column name.

    Usage::

        with get_db() as conn:
            row = conn.execute("SELECT * FROM alerts WHERE id = ?", (1,)).fetchone()

    Parameters
    ----------
    db_path : str | None
        Override the default DB path.
    """
    path = db_path or _get_db_path()
    _ensure_data_dir(path)

    # Reuse per-thread connection when path matches
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

    try:
        yield conn
    except Exception:
        conn.rollback()
        raise


def close_db() -> None:
    """Close the per-thread connection (if any). Call during thread/worker shutdown."""
    conn: sqlite3.Connection | None = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None
        _local.conn_path = None


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def query_one(
    sql: str,
    params: tuple | dict = (),
    db_path: str | None = None,
) -> Optional[dict]:
    """Execute *sql* and return the first row as a ``dict``, or ``None``.

    Parameters
    ----------
    sql : str
        SQL query.
    params : tuple | dict
        Bind parameters.
    db_path : str | None
        Override the default DB path.
    """
    with get_db(db_path) as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def query_all(
    sql: str,
    params: tuple | dict = (),
    db_path: str | None = None,
) -> list[dict]:
    """Execute *sql* and return all rows as a list of ``dict``.

    Parameters
    ----------
    sql : str
        SQL query.
    params : tuple | dict
        Bind parameters.
    db_path : str | None
        Override the default DB path.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def execute(
    sql: str,
    params: tuple | dict = (),
    db_path: str | None = None,
) -> int:
    """Execute a single write statement and commit.

    Returns the ``lastrowid`` (useful for INSERT).

    Parameters
    ----------
    sql : str
        SQL statement.
    params : tuple | dict
        Bind parameters.
    db_path : str | None
        Override the default DB path.
    """
    with get_db(db_path) as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def execute_many(
    sql: str,
    params_seq: list[tuple | dict],
    db_path: str | None = None,
) -> int:
    """Execute *sql* for each set of parameters and commit.

    Returns the number of rows affected (``rowcount`` of the last statement,
    which for ``executemany`` equals the total rows).

    Parameters
    ----------
    sql : str
        SQL statement.
    params_seq : list
        Sequence of bind-parameter tuples/dicts.
    db_path : str | None
        Override the default DB path.
    """
    with get_db(db_path) as conn:
        cursor = conn.executemany(sql, params_seq)
        conn.commit()
        return cursor.rowcount


# ---------------------------------------------------------------------------
# System config helpers (读取 system_config 表)
# ---------------------------------------------------------------------------

def get_sys_config(key: str, default: str = "", db_path: str | None = None) -> str:
    """从 system_config 表读取配置值，不存在则返回 default。"""
    row = query_one(
        "SELECT value FROM system_config WHERE key = ?", (key,), db_path
    )
    return row["value"] if row else default


def set_sys_config(key: str, value: str, db_path: str | None = None) -> None:
    """写入或更新 system_config 表中的配置值。"""
    execute(
        "INSERT INTO system_config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
        db_path,
    )
