import json
import pytest
from agent.planner import PlanStep, AnalysisPlan, format_planning_prompt, format_execution_prompt


SAMPLE_LLM_RESPONSE = json.dumps({
    "goal": "分析来自 WAF 和 NIDS 的可疑扫描告警",
    "steps": [
        {"id": 1, "action": "查询历史记忆中是否有类似扫描行为", "tool": "recall"},
        {"id": 2, "action": "查询源 IP 的历史告警", "tool": "search_alerts"},
        {"id": 3, "action": "查询原始网络日志", "tool": "search_raw_events"},
        {"id": 4, "action": "匹配关联规则", "tool": "match_rules"},
        {"id": 5, "action": "映射到 MITRE ATT&CK", "tool": "map_alert_to_mitre"},
        {"id": 6, "action": "综合研判并给出结论", "tool": None},
    ],
    "estimated_risk": "high"
}, ensure_ascii=False)

SAMPLE_ALERTS = [
    {"id": "alert-001", "source": "WAF", "type": "SQL注入", "src_ip": "10.0.0.5"},
    {"id": "alert-002", "source": "NIDS", "type": "端口扫描", "src_ip": "10.0.0.5"},
]


def test_generate_plan():
    """从 mock LLM JSON 响应解析出 AnalysisPlan"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    assert plan.goal == "分析来自 WAF 和 NIDS 的可疑扫描告警"
    assert len(plan.steps) == 6
    assert plan.steps[0].action == "查询历史记忆中是否有类似扫描行为"
    assert plan.steps[0].tool == "recall"
    assert plan.steps[5].tool is None


def test_plan_schema():
    """验证 plan 包含 goal, steps, estimated_risk"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    d = plan.to_dict()
    assert "goal" in d
    assert "steps" in d
    assert "estimated_risk" in d
    assert d["estimated_risk"] == "high"


def test_dynamic_replan():
    """insert_step 后 steps 数量+1，adjustments 有记录"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    original_count = len(plan.steps)
    plan.insert_step(after_step_id=3, action="检查防火墙日志", tool="search_raw_events")
    assert len(plan.steps) == original_count + 1
    assert len(plan.adjustments) == 1
    assert plan.adjustments[0]["type"] == "insert"
    assert plan.adjustments[0]["after_step_id"] == 3
    # 插入的步骤应该在步骤3之后
    idx_3 = next(i for i, s in enumerate(plan.steps) if s.id == 3)
    assert plan.steps[idx_3 + 1].action == "检查防火墙日志"


def test_skip_step():
    """skip_step 后该步骤 status=skipped"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    plan.skip_step(2, reason="无需查询历史告警")
    step2 = next(s for s in plan.steps if s.id == 2)
    assert step2.status == "skipped"
    assert step2.result_summary == "无需查询历史告警"
    assert len(plan.adjustments) == 1
    assert plan.adjustments[0]["type"] == "skip"


def test_mark_step():
    """mark_step 更新状态和 result_summary"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    plan.mark_step(1, "completed", "发现2条历史记录")
    step1 = next(s for s in plan.steps if s.id == 1)
    assert step1.status == "completed"
    assert step1.result_summary == "发现2条历史记录"


def test_get_next_pending():
    """返回第一个 pending 步骤"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    # 初始时第一个步骤就是 pending
    next_step = plan.get_next_pending()
    assert next_step is not None
    assert next_step.id == 1

    # 标记第一个完成后，应该返回第二个
    plan.mark_step(1, "completed")
    next_step = plan.get_next_pending()
    assert next_step.id == 2


def test_is_complete():
    """所有步骤 completed/skipped 时返回 True"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    assert plan.is_complete() is False

    for step in plan.steps:
        plan.mark_step(step.id, "completed")
    assert plan.is_complete() is True


def test_is_complete_with_skipped():
    """包含 skipped 步骤也算完成"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    for i, step in enumerate(plan.steps):
        if i % 2 == 0:
            plan.mark_step(step.id, "completed")
        else:
            plan.skip_step(step.id, "跳过")
    assert plan.is_complete() is True


def test_from_llm_response_invalid():
    """无效 JSON 时返回默认计划"""
    plan = AnalysisPlan.from_llm_response("this is not json at all")
    assert plan.goal == "分析告警"
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "直接分析告警并给出结论"
    assert plan.estimated_risk == "unknown"


def test_from_llm_response_empty_steps():
    """空步骤列表时返回默认步骤"""
    plan = AnalysisPlan.from_llm_response(json.dumps({"goal": "test", "steps": []}))
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "直接分析告警并给出结论"


def test_format_planning_prompt():
    """生成的 prompt 包含告警数据"""
    prompt = format_planning_prompt(SAMPLE_ALERTS)
    assert "alert-001" in prompt
    assert "SQL注入" in prompt
    assert "10.0.0.5" in prompt
    assert "JSON" in prompt


def test_format_planning_prompt_with_memories():
    """带有历史记忆的 prompt"""
    memories = [{"content": "上次发现类似扫描行为是误报", "score": 0.9}]
    prompt = format_planning_prompt(SAMPLE_ALERTS, memories=memories)
    assert "历史分析记忆" in prompt
    assert "误报" in prompt


def test_format_execution_prompt():
    """生成的 prompt 包含计划进度"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    plan.mark_step(1, "completed", "无历史记录")
    prompt = format_execution_prompt(SAMPLE_ALERTS, plan)
    assert "alert-001" in prompt
    assert "步骤2" in prompt or "步骤1" in prompt
    assert "计划目标" in prompt


def test_get_progress_summary():
    """进度摘要包含关键信息"""
    plan = AnalysisPlan.from_llm_response(SAMPLE_LLM_RESPONSE)
    plan.mark_step(1, "completed", "完成")
    plan.skip_step(2, "跳过")
    summary = plan.get_progress_summary()
    assert "计划目标" in summary
    assert "[x]" in summary
    assert "[-]" in summary
    assert "[ ]" in summary
