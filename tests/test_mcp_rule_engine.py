"""Tests for the rule-engine MCP server."""

import importlib.util
import json
import os

import pytest

# Load the rule-engine server module by file path to avoid name collisions.
_SERVER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "mcp-servers", "rule-engine", "server.py"
)
_spec = importlib.util.spec_from_file_location("rule_engine_server", _SERVER_PATH)
rule_engine_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rule_engine_server)


class TestMatchRules:
    def test_match_sql_injection(self):
        """SQL注入告警 x 10 should match rule-sql-injection-chain (min_count=5)."""
        alerts = [
            {
                "id": i,
                "title": f"SQL注入攻击 #{i}",
                "src_ip": "10.0.0.1",
                "dst_ip": "192.168.1.10",
                "severity": "high",
                "source": "waf",
            }
            for i in range(1, 11)
        ]
        result = json.loads(rule_engine_server.match_rules(json.dumps(alerts)))
        matched_ids = [m["rule"]["id"] for m in result["matched_rules"]]
        assert "rule-sql-injection-chain" in matched_ids

    def test_match_brute_force(self):
        """登录失败告警 x 15 from same src_ip should match rule-brute-force (min_count=10)."""
        alerts = [
            {
                "id": i,
                "title": "登录失败: admin",
                "src_ip": "10.0.0.5",
                "dst_ip": "192.168.1.10",
                "severity": "medium",
                "source": "hids",
            }
            for i in range(1, 16)
        ]
        result = json.loads(rule_engine_server.match_rules(json.dumps(alerts)))
        matched_ids = [m["rule"]["id"] for m in result["matched_rules"]]
        assert "rule-brute-force" in matched_ids

    def test_match_no_rules(self):
        """Unrelated alerts should not match any rule."""
        alerts = [
            {
                "id": 1,
                "title": "系统健康检查通过",
                "src_ip": "10.0.0.1",
                "dst_ip": "192.168.1.10",
                "severity": "info",
                "source": "soc",
            },
            {
                "id": 2,
                "title": "磁盘使用率正常",
                "src_ip": "10.0.0.2",
                "dst_ip": "192.168.1.20",
                "severity": "info",
                "source": "hids",
            },
        ]
        result = json.loads(rule_engine_server.match_rules(json.dumps(alerts)))
        assert result["matched_rules"] == []

    def test_match_lateral_movement(self):
        """Internal-to-internal abnormal connections should match lateral movement."""
        alerts = [
            {
                "id": 1,
                "title": "异常连接: 内网横向扫描",
                "src_ip": "192.168.1.10",
                "dst_ip": "192.168.1.20",
                "severity": "high",
                "source": "nids",
            }
        ]
        result = json.loads(rule_engine_server.match_rules(json.dumps(alerts)))
        matched_ids = [m["rule"]["id"] for m in result["matched_rules"]]
        assert "rule-lateral-movement" in matched_ids

    def test_match_multiple_rules(self):
        """A set of alerts that matches multiple rules at once."""
        alerts = []
        # SQL injection alerts (matches sql-injection-chain)
        for i in range(1, 8):
            alerts.append(
                {
                    "id": i,
                    "title": f"SQL注入攻击 #{i}",
                    "src_ip": "10.0.0.1",
                    "dst_ip": "192.168.1.10",
                    "severity": "high",
                    "source": "waf",
                }
            )
        # Brute force alerts (matches brute-force)
        for i in range(100, 115):
            alerts.append(
                {
                    "id": i,
                    "title": "登录失败",
                    "src_ip": "10.0.0.9",
                    "dst_ip": "192.168.1.10",
                    "severity": "medium",
                    "source": "hids",
                }
            )
        result = json.loads(rule_engine_server.match_rules(json.dumps(alerts)))
        matched_ids = [m["rule"]["id"] for m in result["matched_rules"]]
        assert "rule-sql-injection-chain" in matched_ids
        assert "rule-brute-force" in matched_ids
        assert len(matched_ids) >= 2


class TestGetRules:
    def test_get_rules(self):
        """get_rules should return all rules without internal conditions."""
        result = json.loads(rule_engine_server.get_rules())
        assert "rules" in result
        rules = result["rules"]
        assert len(rules) == 5
        for r in rules:
            assert "id" in r
            assert "name" in r
            assert "description" in r
            assert "risk_boost" in r
            assert "mitre_chain" in r
            # Should NOT contain internal conditions
            assert "conditions" not in r


class TestSequenceRule:
    def test_port_scan_then_exploit(self):
        """Port scan followed by exploit from same IP should match."""
        alerts = [
            {
                "id": 1,
                "title": "nmap 端口扫描",
                "src_ip": "10.0.0.5",
                "dst_ip": "192.168.1.10",
                "severity": "medium",
                "source": "nids",
            },
            {
                "id": 2,
                "title": "漏洞利用尝试",
                "src_ip": "10.0.0.5",
                "dst_ip": "192.168.1.10",
                "severity": "high",
                "source": "waf",
            },
        ]
        result = json.loads(rule_engine_server.match_rules(json.dumps(alerts)))
        matched_ids = [m["rule"]["id"] for m in result["matched_rules"]]
        assert "rule-port-scan-then-exploit" in matched_ids
