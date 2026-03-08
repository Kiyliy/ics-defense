"""mitre-kb MCP Server 单元测试"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# 使用 importlib 直接加载模块，避免 sys.path 冲突
_server_path = Path(__file__).resolve().parent.parent / "mcp-servers" / "mitre-kb" / "server.py"
_spec = importlib.util.spec_from_file_location("mitre_kb_server", str(_server_path))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

lookup_technique = _mod.lookup_technique
lookup_tactic = _mod.lookup_tactic
map_alert_to_mitre = _mod.map_alert_to_mitre


# ---------------------------------------------------------------------------
# lookup_technique
# ---------------------------------------------------------------------------

def test_lookup_technique_found():
    """T0890 → 返回 SQL 注入提权详情"""
    result = json.loads(lookup_technique("T0890"))
    assert result["id"] == "T0890"
    assert result["name"] == "Exploitation for Privilege Escalation"
    assert result["name_zh"] == "漏洞利用提权"
    assert result["tactic"] == "TA0104"
    assert "SQL注入" in result["description"]


def test_lookup_technique_not_found():
    """T9999 → 返回 error"""
    result = json.loads(lookup_technique("T9999"))
    assert "error" in result
    assert "T9999" in result["error"]


# ---------------------------------------------------------------------------
# lookup_tactic
# ---------------------------------------------------------------------------

def test_lookup_tactic():
    """TA0100 → 返回初始访问 + 下属技术列表"""
    result = json.loads(lookup_tactic("TA0100"))
    assert result["id"] == "TA0100"
    assert result["name"] == "Initial Access"
    assert result["name_zh"] == "初始访问"
    assert "techniques" in result
    tech_ids = [t["id"] for t in result["techniques"]]
    assert "T0817" in tech_ids
    assert "T0866" in tech_ids
    assert "T0078" in tech_ids
    assert len(result["techniques"]) >= 3


def test_lookup_tactic_not_found():
    """TA9999 → 返回 error"""
    result = json.loads(lookup_tactic("TA9999"))
    assert "error" in result
    assert "TA9999" in result["error"]


# ---------------------------------------------------------------------------
# map_alert_to_mitre
# ---------------------------------------------------------------------------

def test_map_alert_sql_injection():
    """'SQL注入攻击' → 匹配 T0890"""
    result = json.loads(map_alert_to_mitre("SQL注入攻击"))
    matched_ids = [m["technique"]["id"] for m in result["matched_techniques"]]
    assert "T0890" in matched_ids


def test_map_alert_port_scan():
    """'nmap 端口扫描' → 匹配 T0846"""
    result = json.loads(map_alert_to_mitre("nmap 端口扫描"))
    matched_ids = [m["technique"]["id"] for m in result["matched_techniques"]]
    assert "T0846" in matched_ids


def test_map_alert_multiple():
    """'暴力破解后SQL注入' → 匹配 T0078 + T0890"""
    result = json.loads(map_alert_to_mitre("暴力破解后SQL注入"))
    matched_ids = [m["technique"]["id"] for m in result["matched_techniques"]]
    assert "T0078" in matched_ids
    assert "T0890" in matched_ids
    assert len(matched_ids) >= 2


def test_map_alert_no_match():
    """'正常维护操作' → 空匹配"""
    result = json.loads(map_alert_to_mitre("正常维护操作"))
    assert result["matched_techniques"] == []


def test_map_alert_case_insensitive():
    """大小写不敏感匹配"""
    result_upper = json.loads(map_alert_to_mitre("SQL INJECTION attack"))
    result_lower = json.loads(map_alert_to_mitre("sql injection attack"))
    ids_upper = [m["technique"]["id"] for m in result_upper["matched_techniques"]]
    ids_lower = [m["technique"]["id"] for m in result_lower["matched_techniques"]]
    assert "T0890" in ids_upper
    assert "T0890" in ids_lower
    assert ids_upper == ids_lower
