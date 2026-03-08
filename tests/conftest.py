import pytest
import sqlite3
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# --- 数据库 Schema（与 backend/src/models/db.js 保持一致）---
SCHEMA_SQL = """
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
    mitre_tactic    TEXT,
    mitre_technique TEXT,
    asset_id        INTEGER REFERENCES assets(id),
    status          TEXT DEFAULT 'open',
    raw_event_id    INTEGER REFERENCES raw_events(id),
    created_at      TEXT DEFAULT (datetime('now'))
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
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id     TEXT NOT NULL,
    tool_name    TEXT NOT NULL,
    tool_args    TEXT,
    reason       TEXT,
    status       TEXT DEFAULT 'pending',
    responded_at TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id    TEXT NOT NULL,
    alert_id    TEXT,
    event_type  TEXT NOT NULL,
    data        TEXT,
    token_usage TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_logs(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_alert ON audit_logs(alert_id);
CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_queue(status);
"""


@pytest.fixture
def test_db():
    """内存 SQLite 测试数据库"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def test_db_path(tmp_path):
    """文件型 SQLite 测试数据库（需要路径的场景）"""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.close()
    return db_path


@pytest.fixture
def sample_alerts():
    """测试用聚簇告警样本"""
    return [
        {
            "signature": "abc123",
            "sample": {
                "source": "waf",
                "title": "SQL注入攻击",
                "description": "检测到SQL注入攻击尝试",
                "severity": "high",
                "src_ip": "10.0.0.5",
                "dst_ip": "192.168.1.100",
            },
            "count": 150,
            "severity": "high",
            "first_seen": "2026-03-08T10:00:00Z",
            "last_seen": "2026-03-08T10:35:00Z",
            "source_ips": ["10.0.0.5"],
            "target_ips": ["192.168.1.100"]
        }
    ]


@pytest.fixture
def sample_raw_alerts():
    """测试用原始告警（未聚簇）"""
    return [
        {"source": "waf", "title": "SQL注入攻击", "severity": "high", "src_ip": "10.0.0.5", "dst_ip": "192.168.1.100"},
        {"source": "nids", "title": "端口扫描", "severity": "medium", "src_ip": "10.0.0.5", "dst_ip": "192.168.1.100"},
        {"source": "hids", "title": "异常登录", "severity": "high", "src_ip": "10.0.0.5", "dst_ip": "192.168.1.50"},
    ]


@pytest.fixture
def mock_llm_response():
    """模拟 OpenAI/XAI API 响应的工厂函数"""
    def _make_response(text="分析完毕", tool_calls=None):
        response = MagicMock()
        msg = MagicMock()
        msg.content = text

        if tool_calls:
            mock_tcs = []
            for tc in tool_calls:
                mock_tc = MagicMock()
                mock_tc.id = tc.get("id", f"call_{id(tc)}")
                mock_tc.type = "function"
                mock_tc.function = MagicMock()
                mock_tc.function.name = tc["name"]
                mock_tc.function.arguments = json.dumps(tc.get("input", {}), ensure_ascii=False)
                mock_tcs.append(mock_tc)
            msg.tool_calls = mock_tcs
        else:
            msg.tool_calls = []

        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "tool_calls" if tool_calls else "stop"
        response.choices = [choice]
        response.usage = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50
        return response

    return _make_response


@pytest.fixture
def mock_mcp_client():
    """模拟 MCP Client"""
    client = AsyncMock()
    client.list_tools.return_value = [
        {"name": "search_alerts", "description": "查询告警", "input_schema": {"type": "object", "properties": {}}},
        {"name": "recall", "description": "检索记忆", "input_schema": {"type": "object", "properties": {}}},
    ]
    client.list_tools_for_claude.return_value = [
        {"type": "custom", "name": "search_alerts", "description": "查询告警", "input_schema": {"type": "object", "properties": {}}},
    ]
    client.call_tool.return_value = '{"results": []}'
    client.get_connected_servers.return_value = ["log-search", "rule-engine", "mitre-kb", "action-executor", "notifier", "memory"]
    return client
