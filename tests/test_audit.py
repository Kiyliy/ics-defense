"""Tests for agent/audit.py"""

import time
from datetime import datetime, timedelta

import pytest

from agent.audit import AuditLogger


@pytest.fixture
def audit():
    """使用内存数据库的 AuditLogger"""
    return AuditLogger(db_path=":memory:")


class TestAuditLog:
    def test_tool_call_logged(self, audit):
        """写入一条 tool_call 日志，能查到"""
        audit.log(
            trace_id="t1",
            event_type="tool_call",
            data={"tool": "nmap", "args": ["192.168.1.1"]},
            alert_id="a1",
        )
        trace = audit.get_trace("t1")
        assert len(trace) == 1
        assert trace[0]["event_type"] == "tool_call"
        assert trace[0]["data"]["tool"] == "nmap"
        assert trace[0]["alert_id"] == "a1"

    def test_full_trace(self, audit):
        """写入多条不同 event_type 的日志，get_trace 返回完整链"""
        events = ["alert_received", "plan_generated", "tool_call", "decision_made"]
        for i, evt in enumerate(events):
            audit.log(trace_id="t2", event_type=evt, data={"step": i})

        trace = audit.get_trace("t2")
        assert len(trace) == 4
        types = [r["event_type"] for r in trace]
        assert types == events

    def test_token_tracking(self, audit):
        """多次写入 token_usage，get_total_tokens 汇总正确"""
        audit.log(
            trace_id="t3",
            event_type="llm_call",
            data={},
            token_usage={"input_tokens": 100, "output_tokens": 50},
        )
        audit.log(
            trace_id="t3",
            event_type="llm_call",
            data={},
            token_usage={"input_tokens": 200, "output_tokens": 80},
        )

        totals = audit.get_total_tokens("t3")
        assert totals["input_tokens"] == 300
        assert totals["output_tokens"] == 130
        assert totals["total"] == 430

    def test_get_by_alert(self, audit):
        """按 alert_id 查询"""
        audit.log(trace_id="t4", event_type="alert", data={"x": 1}, alert_id="alert-001")
        audit.log(trace_id="t5", event_type="alert", data={"x": 2}, alert_id="alert-001")
        audit.log(trace_id="t6", event_type="alert", data={"x": 3}, alert_id="alert-002")

        results = audit.get_by_alert("alert-001")
        assert len(results) == 2
        assert all(r["alert_id"] == "alert-001" for r in results)

    def test_get_stats(self, audit):
        """写入数据后统计正确"""
        # 写入几条日志
        audit.log(
            trace_id="s1",
            event_type="llm_call",
            data={},
            token_usage={"input_tokens": 50, "output_tokens": 30},
        )
        audit.log(
            trace_id="s2",
            event_type="llm_call",
            data={},
            token_usage={"input_tokens": 70, "output_tokens": 20},
        )
        audit.log(trace_id="s2", event_type="tool_call", data={})

        stats = audit.get_stats(days=7)
        assert stats["total_analyses"] == 2  # s1, s2
        assert stats["total_tokens"] == 170  # 50+30+70+20
        assert len(stats["daily"]) >= 1

    def test_ensure_table_idempotent(self, audit):
        """多次调用 _ensure_table 不报错"""
        audit._ensure_table()
        audit._ensure_table()
        audit._ensure_table()
        # 写入仍然正常
        audit.log(trace_id="idem", event_type="test", data={"ok": True})
        assert len(audit.get_trace("idem")) == 1
