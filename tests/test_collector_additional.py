"""Additional edge-case tests for collector/severity_filter.py"""

from __future__ import annotations

from collector.severity_filter import SeverityFilter


def test_should_analyze_defaults_false_for_unknown_levels():
    assert SeverityFilter.should_analyze("debug") is False
    assert SeverityFilter.should_analyze("notice") is False


def test_filter_for_agent_defaults_missing_severity_to_store_only():
    alerts = [
        {"title": "missing severity"},
        {"title": "critical event", "severity": "critical"},
        {"title": "uppercase", "severity": "ERROR"},
    ]

    to_analyze, store_only = SeverityFilter.filter_for_agent(alerts)

    assert [alert["title"] for alert in to_analyze] == ["critical event", "uppercase"]
    assert [alert["title"] for alert in store_only] == ["missing severity"]
