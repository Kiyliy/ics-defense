from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agent import agent as agent_module
from agent import planning as planning_module


def test_load_prompts_fall_back_when_files_are_missing(tmp_path: Path):
    with patch.object(planning_module, '_PROMPT_DIR', tmp_path):
        assert '工控安全分析 Agent' in planning_module._load_system_prompt()
        assert 'JSON' in planning_module._load_planning_system_prompt()


def test_parse_decision_extracts_json_from_markdown_code_block():
    content = '分析如下:\n```json\n{"risk_level":"high","confidence":0.8,"attack_chain":[],"recommendation":"block","action_type":"block","rationale":"x"}\n```'
    parsed = agent_module.parse_decision(content)
    assert parsed['risk_level'] == 'high'
    assert parsed['action_type'] == 'block'


def test_parse_decision_extracts_first_outer_json_object():
    content = 'prefix text {"risk_level":"medium","confidence":0.6,"attack_chain":[],"recommendation":"investigate","action_type":"investigate","rationale":"y"} suffix'
    parsed = agent_module.parse_decision(content)
    assert parsed['risk_level'] == 'medium'
    assert parsed['recommendation'] == 'investigate'


def test_parse_decision_returns_default_for_empty_payload():
    parsed = agent_module.parse_decision('   ')
    assert parsed['risk_level'] == 'unknown'
    assert parsed['action_type'] == 'manual_review'
    assert '人工审查' in parsed['recommendation']
