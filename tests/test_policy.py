"""ToolPolicy 单元测试"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.policy import ToolPolicy

YAML_PATH = str(Path(__file__).resolve().parent.parent / "agent" / "tool_policy.yaml")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def policy():
    return ToolPolicy(YAML_PATH)


# ---------------------------------------------------------------------------
# test_auto_tool_direct
# ---------------------------------------------------------------------------

def test_auto_tool_direct(policy: ToolPolicy):
    """search_alerts -> 'auto'"""
    assert policy.get_level("search_alerts") == "auto"


# ---------------------------------------------------------------------------
# test_approve_tool
# ---------------------------------------------------------------------------

def test_approve_tool(policy: ToolPolicy):
    """block_ip -> 'approve'"""
    assert policy.get_level("block_ip") == "approve"


# ---------------------------------------------------------------------------
# test_notify_tool
# ---------------------------------------------------------------------------

def test_notify_tool(policy: ToolPolicy):
    """send_webhook -> 'notify'"""
    assert policy.get_level("send_webhook") == "notify"


# ---------------------------------------------------------------------------
# test_unknown_tool_defaults_approve
# ---------------------------------------------------------------------------

def test_unknown_tool_defaults_approve(policy: ToolPolicy):
    """未知工具 -> 'approve'"""
    assert policy.get_level("totally_unknown_tool") == "approve"


# ---------------------------------------------------------------------------
# test_reload
# ---------------------------------------------------------------------------

def test_reload(tmp_path: Path):
    """修改 yaml 后 reload，新配置生效"""
    cfg = {
        "tool_levels": {
            "auto": ["tool_a"],
            "approve": ["tool_b"],
        },
        "approval_timeout": 100,
    }
    yaml_file = tmp_path / "policy.yaml"
    yaml_file.write_text(yaml.dump(cfg), encoding="utf-8")

    p = ToolPolicy(str(yaml_file))
    assert p.get_level("tool_a") == "auto"
    assert p.get_level("tool_b") == "approve"

    # 修改配置：把 tool_a 移到 notify
    cfg["tool_levels"]["auto"] = []
    cfg["tool_levels"]["notify"] = ["tool_a"]
    yaml_file.write_text(yaml.dump(cfg), encoding="utf-8")

    p.reload()
    assert p.get_level("tool_a") == "notify"


# ---------------------------------------------------------------------------
# test_approval_timeout_config
# ---------------------------------------------------------------------------

def test_approval_timeout_config(policy: ToolPolicy):
    """验证 approval_timeout 读取正确"""
    assert policy.approval_timeout == 300
