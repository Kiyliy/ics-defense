"""Additional edge-case tests for collector/severity_filter.py"""

from __future__ import annotations

from collector.severity_filter import SeverityFilter
from collector.clusterer import AlertClusterer
from collector.normalizer import normalize
from collector.producer import AlertProducer


def test_should_analyze_none_defaults_false():
    assert SeverityFilter.should_analyze(None) is False


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

def test_filter_for_agent_converts_legacy_levels_to_canonical():
    alerts = [
        {"title": "legacy error", "severity": "error"},
        {"title": "legacy warning", "severity": "warning"},
        {"title": "legacy info", "severity": "info"},
    ]

    to_analyze, store_only = SeverityFilter.filter_for_agent(alerts)

    assert [(alert["title"], alert["severity"]) for alert in to_analyze] == [("legacy error", "high")]
    assert [(alert["title"], alert["severity"]) for alert in store_only] == [
        ("legacy warning", "medium"),
        ("legacy info", "low"),
    ]



def test_clusterer_updates_first_last_seen_for_out_of_order_timestamps():
    clusterer = AlertClusterer()
    clusterer.add({
        "source": "waf",
        "title": "Same Alert",
        "severity": "error",
        "src_ip": "10.0.0.1",
        "dst_ip": "192.168.1.1",
        "timestamp": "2025-01-01T02:00:00+00:00",
    })
    clusterer.add({
        "source": "waf",
        "title": "Same Alert",
        "severity": "error",
        "src_ip": "10.0.0.1",
        "dst_ip": "192.168.1.1",
        "timestamp": "2025-01-01T01:00:00+00:00",
    })

    cluster = clusterer.get_clusters()[0]
    assert cluster.first_seen == "2025-01-01T01:00:00+00:00"
    assert cluster.last_seen == "2025-01-01T02:00:00+00:00"


def test_normalize_accepts_uppercase_source_and_normalizes_timestamp():
    result = normalize("WAF", {
        "rule_name": "SQL Injection",
        "severity": "高",
        "timestamp": "2025-01-01T00:00:00Z",
    })

    assert result.source == "waf"
    assert result.timestamp == "2025-01-01T00:00:00Z"


def test_producer_rejects_non_dict_payload():
    producer = AlertProducer()

    try:
        producer.publish(["bad-payload"])
        raised = False
    except TypeError:
        raised = True

    assert raised is True

def test_should_analyze_accepts_backend_high_severity():
    assert SeverityFilter.should_analyze("high") is True


def test_filter_for_agent_accepts_mixed_severity_vocabularies():
    alerts = [
        {"title": "critical event", "severity": "critical"},
        {"title": "backend high", "severity": "high"},
        {"title": "collector error", "severity": "error"},
        {"title": "backend medium", "severity": "medium"},
        {"title": "collector warning", "severity": "warning"},
    ]

    to_analyze, store_only = SeverityFilter.filter_for_agent(alerts)

    assert [alert["title"] for alert in to_analyze] == [
        "critical event",
        "backend high",
        "collector error",
    ]
    assert [alert["title"] for alert in store_only] == [
        "backend medium",
        "collector warning",
    ]
