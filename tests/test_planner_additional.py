"""Additional edge-case tests for agent/planner.py."""

from __future__ import annotations

import pytest

from agent.planner import AnalysisPlan, PlanStep, format_execution_prompt


def test_mark_step_raises_for_missing_step():
    plan = AnalysisPlan(goal="分析告警", steps=[PlanStep(id=1, action="查询", tool="search_alerts")])

    with pytest.raises(ValueError):
        plan.mark_step(999, "completed")


def test_insert_step_uses_next_max_id_and_preserves_order():
    plan = AnalysisPlan(
        goal="分析告警",
        steps=[
            PlanStep(id=1, action="第一步", tool="a"),
            PlanStep(id=5, action="第二步", tool="b"),
        ],
    )

    plan.insert_step(after_step_id=1, action="插入步骤", tool="c")

    assert [step.action for step in plan.steps] == ["第一步", "插入步骤", "第二步"]
    assert plan.steps[1].id == 6
    assert plan.adjustments[-1]["new_step_id"] == 6


def test_progress_summary_and_execution_prompt_for_completed_plan():
    plan = AnalysisPlan(
        goal="分析告警",
        steps=[PlanStep(id=1, action="完成步骤", tool=None, status="completed", result_summary="ok")],
        estimated_risk="high",
    )

    summary = plan.get_progress_summary()
    prompt = format_execution_prompt([{"id": "a1"}], plan)

    assert "计划目标: 分析告警" in summary
    assert "[x]" in summary
    assert "所有步骤已完成，请给出最终分析结论。" in prompt
