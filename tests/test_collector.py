"""
Collector 模块测试

覆盖 normalizer、clusterer、severity_filter、producer 四个子模块。
"""

import sys
import os
import json
from unittest.mock import MagicMock, patch

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collector.normalizer import (
    normalize, normalize_waf, normalize_nids, normalize_hids,
    normalize_pikachu, normalize_soc, NormalizedAlert,
)
from collector.clusterer import AlertClusterer, ClusteredAlert
from collector.severity_filter import SeverityFilter
from collector.producer import AlertProducer


# ============================================================
# Normalizer Tests
# ============================================================

class TestNormalizeWAF:
    def test_normalize_waf(self):
        raw = {
            "rule_name": "SQL Injection Detected",
            "severity": "高",
            "src_ip": "10.0.0.1",
            "dst_ip": "192.168.1.1",
            "reason": "Detected SQL injection in parameter",
            "url": "/api/login",
        }
        result = normalize_waf(raw)
        assert isinstance(result, NormalizedAlert)
        assert result.source == "waf"
        assert result.title == "SQL Injection Detected"
        assert result.severity == "high"
        assert result.src_ip == "10.0.0.1"
        assert result.dst_ip == "192.168.1.1"
        assert result.mitre_tactic == "Execution"
        assert result.mitre_technique == "T0807"
        assert result.description == "Detected SQL injection in parameter"

    def test_normalize_waf_fallback_fields(self):
        raw = {
            "event_type": "XSS Attack",
            "risk_level": "严重",
            "remote_addr": "10.0.0.2",
            "server_addr": "192.168.1.2",
        }
        result = normalize_waf(raw)
        assert result.title == "XSS Attack"
        assert result.severity == "critical"
        assert result.src_ip == "10.0.0.2"
        assert result.dst_ip == "192.168.1.2"


class TestNormalizeNIDS:
    def test_normalize_nids(self):
        raw = {
            "alert": {
                "signature": "ET SCAN Nmap SYN Scan",
                "signature_id": 2001219,
                "severity": 1,
                "category": "Attempted Information Leak",
            },
            "src_ip": "10.0.0.5",
            "dest_ip": "192.168.1.10",
            "proto": "TCP",
        }
        result = normalize_nids(raw)
        assert result.source == "nids"
        assert result.severity == "critical"
        assert result.title == "ET SCAN Nmap SYN Scan"
        assert "SID:2001219" in result.description
        assert result.src_ip == "10.0.0.5"
        assert result.dst_ip == "192.168.1.10"
        assert result.protocol == "TCP"
        assert result.mitre_tactic == "Reconnaissance"

    def test_normalize_nids_severity_mapping(self):
        for sev, expected in [(1, "critical"), (2, "high"), (3, "medium"), (4, "low")]:
            raw = {"alert": {"severity": sev}}
            result = normalize_nids(raw)
            assert result.severity == expected, f"severity {sev} should map to {expected}"


class TestNormalizeHIDS:
    def test_normalize_hids(self):
        raw = {
            "rule": {
                "id": "5502",
                "description": "Login session opened",
                "level": 3,
                "groups": ["syslog", "authentication"],
            },
            "agent": {"ip": "192.168.1.20"},
            "data": {"srcip": "10.0.0.8"},
        }
        result = normalize_hids(raw)
        assert result.source == "hids"
        assert result.severity == "low"  # level 3 < 4
        assert result.title == "Login session opened"
        assert result.src_ip == "10.0.0.8"
        assert result.dst_ip == "192.168.1.20"
        assert "Rule:5502" in result.description
        assert result.mitre_tactic == "Initial Access"

    def test_normalize_hids_severity_mapping(self):
        for level, expected in [(3, "low"), (4, "medium"), (8, "high"), (12, "critical"), (15, "critical")]:
            raw = {"rule": {"level": level}}
            result = normalize_hids(raw)
            assert result.severity == expected, f"level {level} should map to {expected}"


class TestNormalizePikachu:
    def test_normalize_pikachu(self):
        raw = {
            "vuln_type": "XSS Reflected",
            "payload": "<script>alert(1)</script>",
            "src_ip": "10.0.0.3",
            "target_ip": "192.168.1.5",
        }
        result = normalize_pikachu(raw)
        assert result.source == "pikachu"
        assert result.severity == "medium"
        assert result.title == "XSS Reflected"
        assert result.src_ip == "10.0.0.3"
        assert result.dst_ip == "192.168.1.5"
        assert result.mitre_tactic == "Execution"


class TestNormalizeSOC:
    def test_normalize_soc(self):
        raw = {
            "title": "Suspicious scan activity",
            "severity": "medium",
            "src_ip": "10.0.0.9",
            "dst_ip": "192.168.1.30",
            "description": "Port scan detected from external IP",
        }
        result = normalize_soc(raw)
        assert result.source == "soc"
        assert result.severity == "medium"
        assert result.title == "Suspicious scan activity"
        assert result.description == "Port scan detected from external IP"
        assert result.mitre_tactic == "Reconnaissance"


class TestNormalizeDispatch:
    def test_normalize_unknown_source(self):
        raw = {"title": "Unknown event", "severity": "high"}
        result = normalize("unknown_source", raw)
        assert isinstance(result, NormalizedAlert)
        # Falls back to normalize_soc
        assert result.title == "Unknown event"
        assert result.severity == "high"

    def test_normalize_dispatch_waf(self):
        raw = {"rule_name": "Test", "severity": "低"}
        result = normalize("waf", raw)
        assert result.source == "waf"

    def test_to_dict(self):
        raw = {"rule_name": "Test", "severity": "低"}
        result = normalize("waf", raw)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["source"] == "waf"
        assert "title" in d
        assert "severity" in d


# ============================================================
# Clusterer Tests
# ============================================================

class TestClusterer:
    def _make_alert(self, title="Test Alert", src_ip="10.0.0.1", dst_ip="192.168.1.1",
                    severity="high", source="waf", timestamp=None):
        return {
            "source": source,
            "title": title,
            "severity": severity,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "timestamp": timestamp or "2025-01-01T00:00:00+00:00",
        }

    def test_cluster_same_alerts(self):
        """100条相同告警 -> 聚簇为1条，count=100"""
        clusterer = AlertClusterer()
        for _ in range(100):
            clusterer.add(self._make_alert())
        clusters = clusterer.get_clusters()
        assert len(clusters) == 1
        assert clusters[0].count == 100

    def test_cluster_different_alerts(self):
        """3条不同告警 -> 3个聚簇"""
        clusterer = AlertClusterer()
        clusterer.add(self._make_alert(title="Alert A"))
        clusterer.add(self._make_alert(title="Alert B"))
        clusterer.add(self._make_alert(title="Alert C"))
        clusters = clusterer.get_clusters()
        assert len(clusters) == 3

    def test_cluster_preserves_time_range(self):
        """first_seen/last_seen 正确"""
        clusterer = AlertClusterer()
        clusterer.add(self._make_alert(timestamp="2025-01-01T00:00:00+00:00"))
        clusterer.add(self._make_alert(timestamp="2025-01-01T01:00:00+00:00"))
        clusterer.add(self._make_alert(timestamp="2025-01-01T02:00:00+00:00"))
        clusters = clusterer.get_clusters()
        assert len(clusters) == 1
        assert clusters[0].first_seen == "2025-01-01T00:00:00+00:00"
        assert clusters[0].last_seen == "2025-01-01T02:00:00+00:00"

    def test_cluster_collects_ips(self):
        """source_ips/target_ips 去重收集"""
        clusterer = AlertClusterer()
        # Same title/severity but different IPs won't cluster together
        # because src_ip is part of the signature. Use same key fields.
        alert_base = self._make_alert()
        clusterer.add(alert_base)
        # Add same alert again - same IP, should not duplicate
        clusterer.add(alert_base)
        clusters = clusterer.get_clusters()
        assert len(clusters) == 1
        assert clusters[0].source_ips == ["10.0.0.1"]
        assert clusters[0].target_ips == ["192.168.1.1"]

    def test_flush_clears(self):
        """flush 后 clusters 为空"""
        clusterer = AlertClusterer()
        clusterer.add(self._make_alert())
        clusterer.add(self._make_alert(title="Another"))
        result = clusterer.flush()
        assert len(result) == 2
        assert len(clusterer.get_clusters()) == 0

    def test_clustered_alert_to_dict(self):
        clusterer = AlertClusterer()
        clusterer.add(self._make_alert())
        clusters = clusterer.get_clusters()
        d = clusters[0].to_dict()
        assert isinstance(d, dict)
        assert "signature" in d
        assert "count" in d
        assert "sample" in d


# ============================================================
# SeverityFilter Tests
# ============================================================

class TestSeverityFilter:
    def test_should_analyze_error(self):
        assert SeverityFilter.should_analyze("error") is True

    def test_should_analyze_critical(self):
        assert SeverityFilter.should_analyze("critical") is True

    def test_should_analyze_warning(self):
        assert SeverityFilter.should_analyze("warning") is False

    def test_should_analyze_info(self):
        assert SeverityFilter.should_analyze("info") is False

    def test_should_analyze_case_insensitive(self):
        assert SeverityFilter.should_analyze("CRITICAL") is True
        assert SeverityFilter.should_analyze("Error") is True

    def test_filter_for_agent(self):
        alerts = [
            {"severity": "critical", "title": "A"},
            {"severity": "error", "title": "B"},
            {"severity": "warning", "title": "C"},
            {"severity": "info", "title": "D"},
            {"severity": "error", "title": "E"},
        ]
        to_analyze, store_only = SeverityFilter.filter_for_agent(alerts)
        assert len(to_analyze) == 3  # critical + 2x error
        assert len(store_only) == 2  # warning + info
        assert all(a["severity"] in ("critical", "high") for a in to_analyze)
        assert all(a["severity"] in ("medium", "low") for a in store_only)


# ============================================================
# Producer Tests
# ============================================================

class TestProducer:
    def test_redis_publish(self):
        """mock redis，验证 xadd 被调用"""
        producer = AlertProducer()
        mock_client = MagicMock()
        mock_client.xadd.return_value = "1234567890-0"
        producer._client = mock_client

        alert_data = {"signature": "abc123", "count": 5}
        msg_id = producer.publish(alert_data)

        mock_client.xadd.assert_called_once_with(
            "ics:alerts",
            {"data": json.dumps(alert_data, ensure_ascii=False)},
        )
        assert msg_id == "1234567890-0"

    def test_redis_publish_batch(self):
        """批量发布，验证调用次数"""
        producer = AlertProducer()
        mock_client = MagicMock()
        mock_client.xadd.return_value = "1234567890-0"
        producer._client = mock_client

        alerts = [{"id": i} for i in range(5)]
        results = producer.publish_batch(alerts)

        assert len(results) == 5
        assert mock_client.xadd.call_count == 5

    def test_producer_close(self):
        producer = AlertProducer()
        mock_client = MagicMock()
        producer._client = mock_client
        producer.close()
        mock_client.close.assert_called_once()
        assert producer._client is None
