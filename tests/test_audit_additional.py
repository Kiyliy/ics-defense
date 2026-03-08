"""Additional edge-case tests for agent/audit.py"""

from __future__ import annotations

from datetime import datetime, timedelta

from agent.audit import AuditLogger


def test_log_accepts_empty_data_and_token_usage():
    audit = AuditLogger(db_path=":memory:")
    audit.log(trace_id="trace-empty", event_type="heartbeat", data=None, token_usage=None)

    rows = audit.get_trace("trace-empty")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "heartbeat"
    assert rows[0]["data"] is None
    assert rows[0]["token_usage"] is None


def test_get_stats_excludes_old_records():
    audit = AuditLogger(db_path=":memory:")
    audit.log(
        trace_id="recent-trace",
        event_type="llm_call",
        data={},
        token_usage={"input_tokens": 10, "output_tokens": 5},
    )
    audit.log(
        trace_id="old-trace",
        event_type="llm_call",
        data={},
        token_usage={"input_tokens": 100, "output_tokens": 50},
    )

    cutoff_time = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    audit._get_conn().execute(
        "UPDATE audit_logs SET created_at = ? WHERE trace_id = ?",
        (cutoff_time, "old-trace"),
    )
    audit._get_conn().commit()

    stats = audit.get_stats(days=7)
    assert stats["total_analyses"] == 1
    assert stats["total_tokens"] == 15
    assert all(day["tokens"] <= 15 for day in stats["daily"])
