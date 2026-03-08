"""Additional edge-case tests for agent/guard.py."""

from __future__ import annotations

import asyncio

import pytest

from agent.guard import AgentGuard, AgentStuck


def test_stuck_detection_ignores_non_consecutive_repetition():
    guard = AgentGuard({"stuck_threshold": 3})
    guard.reset()
    guard.check_stuck("search_alerts", {"q": 1})
    guard.check_stuck("match_rules", {"q": 1})
    guard.check_stuck("search_alerts", {"q": 1})


@pytest.mark.asyncio
async def test_execute_with_retry_returns_timeout_error_after_all_attempts():
    guard = AgentGuard({"step_timeout": 0.01, "max_retries": 1})
    guard.reset()

    async def slow_tool(_name, _args):
        await asyncio.sleep(0.05)
        return {"status": "ok"}

    result = await guard.execute_with_retry(slow_tool, "search_alerts", {})

    assert "error" in result
    assert "超时" in result["error"]
    assert guard.step_count == 1


@pytest.mark.asyncio
async def test_execute_with_retry_retries_connection_errors_exactly():
    guard = AgentGuard({"max_retries": 2, "step_timeout": 1})
    guard.reset()
    calls = 0

    async def broken_tool(_name, _args):
        nonlocal calls
        calls += 1
        raise ConnectionError("network down")

    result = await guard.execute_with_retry(broken_tool, "block_ip", {"ip": "1.2.3.4"})

    assert calls == 3
    assert "network down" in result["error"]


def test_stuck_detection_raises_for_consecutive_same_calls():
    guard = AgentGuard({"stuck_threshold": 2})
    guard.reset()
    guard.check_stuck("search_alerts", {"severity": "high"})

    with pytest.raises(AgentStuck):
        guard.check_stuck("search_alerts", {"severity": "high"})
