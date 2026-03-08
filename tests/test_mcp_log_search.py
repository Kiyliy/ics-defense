"""Tests for the log-search MCP server.

Uses an in-memory SQLite database so no real DB is needed.
"""

import importlib.util
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

# Load the log-search server module by file path to avoid name collisions.
_SERVER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "mcp-servers", "log-search", "server.py"
)
_spec = importlib.util.spec_from_file_location("log_search_server", _SERVER_PATH)
log_search_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(log_search_server)


def _create_test_db():
    """Create an in-memory SQLite database with test data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE alerts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source        TEXT NOT NULL,
            severity      TEXT DEFAULT 'medium',
            title         TEXT NOT NULL,
            description   TEXT,
            src_ip        TEXT,
            dst_ip        TEXT,
            mitre_tactic  TEXT,
            mitre_technique TEXT,
            asset_id      INTEGER,
            status        TEXT DEFAULT 'open',
            raw_event_id  INTEGER,
            created_at    TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE raw_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT NOT NULL,
            raw_json    TEXT NOT NULL,
            received_at TEXT DEFAULT (datetime('now'))
        )
        """
    )

    now = datetime.now(timezone.utc)

    # Insert test alerts
    alerts_data = [
        ("waf", "high", "SQL注入攻击", "检测到SQL注入", "10.0.0.1", "192.168.1.10",
         None, None, None, "open", None, (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")),
        ("nids", "critical", "端口扫描", "检测到端口扫描", "10.0.0.2", "192.168.1.20",
         None, None, None, "open", None, (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")),
        ("hids", "medium", "文件修改", "敏感文件被修改", "192.168.1.5", "192.168.1.10",
         None, None, None, "analyzing", None, (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")),
        ("waf", "high", "XSS攻击", "检测到XSS", "10.0.0.1", "192.168.1.30",
         None, None, None, "resolved", None, (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")),
        ("soc", "low", "正常登录", "用户登录", "10.0.0.3", "192.168.1.10",
         None, None, None, "open", None, (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")),
    ]
    for a in alerts_data:
        conn.execute(
            """INSERT INTO alerts
               (source, severity, title, description, src_ip, dst_ip,
                mitre_tactic, mitre_technique, asset_id, status, raw_event_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            a,
        )

    # Insert test raw events
    raw_data = [
        ("waf", json.dumps({"src_ip": "10.0.0.1", "payload": "' OR 1=1--"}),
         (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")),
        ("nids", json.dumps({"src_ip": "10.0.0.2", "ports": [22, 80, 443]}),
         (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")),
        ("hids", json.dumps({"src_ip": "192.168.1.5", "file": "/etc/passwd"}),
         (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")),
    ]
    for r in raw_data:
        conn.execute(
            "INSERT INTO raw_events (source, raw_json, received_at) VALUES (?, ?, ?)",
            r,
        )

    conn.commit()
    return conn


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch):
    """Patch get_db to return the in-memory test database."""
    test_conn = _create_test_db()

    def patched_get_db():
        return test_conn

    monkeypatch.setattr(log_search_server, "get_db", patched_get_db)
    yield
    test_conn.close()


class TestSearchAlerts:
    def test_search_alerts_no_filter(self):
        result = json.loads(log_search_server.search_alerts(hours=48))
        assert isinstance(result, list)
        assert len(result) == 5

    def test_search_alerts_by_severity(self):
        result = json.loads(log_search_server.search_alerts(severity="high", hours=48))
        assert len(result) == 2
        for alert in result:
            assert alert["severity"] == "high"

    def test_search_alerts_by_src_ip(self):
        result = json.loads(log_search_server.search_alerts(src_ip="10.0.0.1", hours=48))
        assert len(result) == 2
        for alert in result:
            assert alert["src_ip"] == "10.0.0.1"

    def test_search_alerts_empty(self):
        result = json.loads(log_search_server.search_alerts(src_ip="99.99.99.99", hours=48))
        assert result == []


class TestSearchRawEvents:
    def test_search_raw_events(self):
        result = json.loads(log_search_server.search_raw_events(hours=48))
        assert isinstance(result, list)
        assert len(result) == 3

    def test_search_raw_events_by_source(self):
        result = json.loads(log_search_server.search_raw_events(source="waf", hours=48))
        assert len(result) == 1
        assert result[0]["source"] == "waf"


class TestGetAlertContext:
    def test_get_alert_context(self):
        result = json.loads(log_search_server.get_alert_context(alert_id=1, window_minutes=180))
        assert "target_alert" in result
        assert result["target_alert"]["id"] == 1
        assert "context_alerts" in result
        assert isinstance(result["context_alerts"], list)
        # Alert 2 is within 180 minutes of alert 1
        assert len(result["context_alerts"]) > 0
        assert "raw_events" in result

    def test_get_alert_context_not_found(self):
        result = json.loads(log_search_server.get_alert_context(alert_id=9999))
        assert "error" in result
