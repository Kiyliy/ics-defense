"""action-executor MCP Server 单元测试"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# 使用 importlib 直接加载模块，避免 sys.path 冲突
_server_path = Path(__file__).resolve().parent.parent / "mcp-servers" / "action-executor" / "server.py"
_spec = importlib.util.spec_from_file_location("action_executor_server", str(_server_path))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

block_ip = _mod.block_ip
isolate_host = _mod.isolate_host
add_watch = _mod.add_watch
execution_log = _mod.execution_log


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_log():
    """每个测试前清空执行日志"""
    execution_log.clear()
    yield
    execution_log.clear()


# ---------------------------------------------------------------------------
# block_ip
# ---------------------------------------------------------------------------

def test_block_ip():
    """阻断IP → 返回 status=executed"""
    result = json.loads(block_ip("192.168.1.100", reason="恶意扫描"))
    assert result["status"] == "executed"
    assert result["action"] == "block_ip"
    assert result["ip"] == "192.168.1.100"


def test_block_ip_with_duration():
    """指定 duration_hours"""
    result = json.loads(block_ip("10.0.0.1", reason="测试", duration_hours=48))
    assert result["duration_hours"] == 48
    assert result["status"] == "executed"


# ---------------------------------------------------------------------------
# isolate_host
# ---------------------------------------------------------------------------

def test_isolate_host():
    """隔离主机 → 返回 status=executed"""
    result = json.loads(isolate_host("192.168.1.200", reason="疑似被控"))
    assert result["status"] == "executed"
    assert result["action"] == "isolate_host"
    assert result["ip"] == "192.168.1.200"


# ---------------------------------------------------------------------------
# add_watch
# ---------------------------------------------------------------------------

def test_add_watch():
    """添加监控 → 返回 status=created"""
    result = json.loads(add_watch("192.168.1.50", watch_type="alert", description="可疑流量监控"))
    assert result["status"] == "created"
    assert result["target"] == "192.168.1.50"
    assert result["watch_type"] == "alert"


# ---------------------------------------------------------------------------
# execution_log
# ---------------------------------------------------------------------------

def test_execution_log_recorded():
    """执行后 execution_log 有记录"""
    assert len(execution_log) == 0
    block_ip("1.2.3.4", reason="test")
    assert len(execution_log) == 1
    isolate_host("5.6.7.8", reason="test2")
    assert len(execution_log) == 2
    add_watch("9.10.11.12")
    assert len(execution_log) == 3


def test_block_ip_fields():
    """返回的 JSON 包含所有必要字段"""
    result = json.loads(block_ip("10.0.0.5", reason="测试字段", duration_hours=12))
    required_fields = ["action", "ip", "reason", "duration_hours", "executed_at", "status"]
    for field in required_fields:
        assert field in result, f"Missing field: {field}"
