from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from agent.audit import AuditLogger
from agent import service


class DummyMCPClient:
    async def connect_all(self):
        return None

    async def refresh_tools(self):
        return None

    async def close(self):
        return None

    def get_connected_servers(self):
        return ["dummy"]


def _insert_alert(conn, alert_id: int, title: str = "SQL Injection", severity: str = "high"):
    conn.execute(
        """
        INSERT INTO alerts (id, source, severity, title, description, src_ip, dst_ip, status, created_at)
        VALUES (?, 'waf', ?, ?, 'desc', '10.0.0.1', '192.168.1.10', 'open', '2026-03-08T10:00:00Z')
        """,
        (alert_id, severity, title),
    )
    conn.commit()


def _make_client(monkeypatch, db_path: str):
    service._running_tasks.clear()
    monkeypatch.setattr(service, "DB_PATH", db_path)
    monkeypatch.setattr(service, "_mcp_client", None)
    monkeypatch.setattr(service, "create_client_from_config", lambda _path: DummyMCPClient())
    return TestClient(service.app)


def test_analyze_returns_404_when_alerts_not_found(monkeypatch, test_db_path):
    with _make_client(monkeypatch, test_db_path) as client:
        response = client.post("/analyze", json={"alert_ids": [999]})

    assert response.status_code == 404
    assert response.json()["detail"] == "未找到指定告警"


def test_analyze_rejects_empty_alert_ids(monkeypatch, test_db_path):
    with _make_client(monkeypatch, test_db_path) as client:
        response = client.post("/analyze", json={"alert_ids": []})

    assert response.status_code == 422


def test_fetch_alerts_by_ids_returns_empty_for_empty_ids(monkeypatch, test_db_path):
    monkeypatch.setattr(service, "DB_PATH", test_db_path)
    assert service._fetch_alerts_by_ids([]) == []


def test_analyze_starts_task_and_exposes_status(monkeypatch, test_db_path):
    conn = service.sqlite3.connect(test_db_path)
    _insert_alert(conn, 1, title="SQL Injection")
    _insert_alert(conn, 2, title="SQL Injection")
    conn.close()

    async def fake_run_analysis(trace_id, clustered_alerts, model):
        service._running_tasks[trace_id]["status"] = "completed"
        service._running_tasks[trace_id]["result"] = {
            "risk_level": "high",
            "recommendation": "block source ip",
        }
        assert len(clustered_alerts) == 1
        assert clustered_alerts[0]["count"] == 2
        assert clustered_alerts[0]["signature"] == 'SQL Injection|waf|10.0.0.1|192.168.1.10'
        assert model == "test-model"

    monkeypatch.setattr(service, "_run_analysis", fake_run_analysis)

    with _make_client(monkeypatch, test_db_path) as client:
        response = client.post("/analyze", json={"alert_ids": [1, 2], "model": "test-model"})
        body = response.json()

        assert response.status_code == 200
        assert body["status"] == "started"
        trace_id = body["trace_id"]

        detail = client.get(f"/analyze/{trace_id}")
        detail_body = detail.json()
        assert detail.status_code == 200
        assert detail_body["alert_ids"] == [1, 2]
        assert detail_body["status"] in {"started", "completed"}


def test_get_analysis_reconstructs_result_from_audit_logs(monkeypatch, test_db_path):
    audit = AuditLogger(test_db_path)
    audit.log("trace-from-audit", "tool_call", {"tool": "search_alerts"})
    audit.log("trace-from-audit", "decision_made", {"risk_level": "critical", "action_type": "block"})
    audit.log(
        "trace-from-audit",
        "analysis_finished",
        {"risk_level": "critical"},
        token_usage={"input_tokens": 12, "output_tokens": 8},
    )
    audit.close()

    with _make_client(monkeypatch, test_db_path) as client:
        response = client.get("/analyze/trace-from-audit")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "completed"
    assert body["result"]["risk_level"] == "critical"
    assert body["token_usage"] == {"input_tokens": 12, "output_tokens": 8, "total": 20}
    assert len(body["audit_logs"]) == 3


def test_get_analysis_returns_error_status_when_guard_exception_logged(monkeypatch, test_db_path):
    audit = AuditLogger(test_db_path)
    audit.log("trace-error", "guard_exception", {"message": "policy denied"})
    audit.close()

    with _make_client(monkeypatch, test_db_path) as client:
        response = client.get("/analyze/trace-error")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["result"] is None


def test_approval_respond_updates_pending_record(monkeypatch, test_db_path):
    conn = service.sqlite3.connect(test_db_path)
    conn.execute(
        "INSERT INTO approval_queue (id, trace_id, tool_name, tool_args, reason, status) VALUES (1, 't-1', 'block_ip', '{}', 'need approval', 'pending')"
    )
    conn.commit()
    conn.close()

    with _make_client(monkeypatch, test_db_path) as client:
        ok = client.post("/approval/1/respond", json={"status": "approved", "reason": "LGTM"})
        duplicate = client.post("/approval/1/respond", json={"status": "rejected", "reason": "too late"})
        missing = client.post("/approval/999/respond", json={"status": "approved"})

    assert ok.status_code == 200
    assert ok.json()["message"] == "审批已批准"
    assert duplicate.status_code == 400
    assert "审批已处理" in duplicate.json()["detail"]
    assert missing.status_code == 404


def test_chat_maps_auth_and_rate_limit_errors(monkeypatch, test_db_path):
    class FakeCreate:
        def __init__(self, error):
            self.error = error

        async def create(self, **_kwargs):
            raise self.error

    class FakeClient:
        def __init__(self, error):
            self.chat = type("Chat", (), {"completions": FakeCreate(error)})()

    with _make_client(monkeypatch, test_db_path) as client:
        with patch("agent.service.AsyncOpenAI", return_value=FakeClient(Exception("401 unauthorized"))):
            unauthorized = client.post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})

        with patch("agent.service.AsyncOpenAI", return_value=FakeClient(Exception("429 rate limit"))):
            rate_limited = client.post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert unauthorized.status_code == 401
    assert unauthorized.json()["detail"] == "API Key 无效"
    assert rate_limited.status_code == 429
    assert rate_limited.json()["detail"] == "API 请求频率超限"
