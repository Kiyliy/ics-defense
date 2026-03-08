from __future__ import annotations

import pytest

from agent.planner import AnalysisPlan, PlanStep, format_execution_prompt


def test_from_llm_response_falls_back_on_invalid_json():
    plan = AnalysisPlan.from_llm_response('not-json')

    assert plan.goal == '分析告警'
    assert len(plan.steps) == 1
    assert plan.steps[0].action == '直接分析告警并给出结论'
    assert plan.steps[0].tool is None


def test_mark_step_raises_for_unknown_step_id():
    plan = AnalysisPlan(goal='demo', steps=[PlanStep(id=1, action='a', tool=None)])

    with pytest.raises(ValueError, match='Step 99 not found'):
        plan.mark_step(99, 'completed')


def test_insert_step_raises_when_anchor_missing():
    plan = AnalysisPlan(goal='demo', steps=[PlanStep(id=1, action='a', tool=None)])

    with pytest.raises(ValueError, match='Step 2 not found'):
        plan.insert_step(2, 'b', 'tool_b')


def test_execution_prompt_requests_final_conclusion_when_complete():
    plan = AnalysisPlan(goal='demo', steps=[PlanStep(id=1, action='done', tool=None, status='completed')])

    prompt = format_execution_prompt([{'signature': 'sig-1'}], plan)

    assert '所有步骤已完成，请给出最终分析结论。' in prompt
    assert '请执行下一步' not in prompt
