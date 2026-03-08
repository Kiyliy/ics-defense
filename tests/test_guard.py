"""AgentGuard 单元测试"""

from __future__ import annotations

import asyncio
import sys
import time
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from agent.guard import (
    AgentGuard,
    AgentStuck,
    MaxStepsExceeded,
    TotalTimeoutExceeded,
)


# ---------------------------------------------------------------------------
# test_max_steps_exceeded
# ---------------------------------------------------------------------------

def test_max_steps_exceeded():
    """模拟超过 20 步，期望 MaxStepsExceeded"""
    guard = AgentGuard({"max_steps": 5})
    guard.reset()
    for _ in range(5):
        guard.check_before_step()
        guard.step_count += 1

    with pytest.raises(MaxStepsExceeded):
        guard.check_before_step()


# ---------------------------------------------------------------------------
# test_stuck_detection
# ---------------------------------------------------------------------------

def test_stuck_detection():
    """连续 3 次相同调用，期望 AgentStuck"""
    guard = AgentGuard({"stuck_threshold": 3})
    guard.reset()
    guard.check_stuck("search_alerts", {"query": "x"})
    guard.check_stuck("search_alerts", {"query": "x"})
    with pytest.raises(AgentStuck):
        guard.check_stuck("search_alerts", {"query": "x"})


# ---------------------------------------------------------------------------
# test_tool_retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_retry():
    """第1次超时第2次成功，期望成功返回"""
    guard = AgentGuard({"step_timeout": 1, "max_retries": 2})
    guard.reset()

    call_count = 0

    async def flaky_tool(name, args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(10)  # 触发超时
        return {"status": "ok"}

    result = await guard.execute_with_retry(flaky_tool, "search_alerts", {})
    assert result == {"status": "ok"}
    assert call_count == 2


# ---------------------------------------------------------------------------
# test_mcp_fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_fallback():
    """工具完全不可用，期望返回 error dict"""
    guard = AgentGuard({"step_timeout": 1, "max_retries": 1})
    guard.reset()

    async def broken_tool(name, args):
        raise ConnectionError("service unavailable")

    result = await guard.execute_with_retry(broken_tool, "block_ip", {"ip": "1.2.3.4"})
    assert isinstance(result, dict)
    assert "error" in result


# ---------------------------------------------------------------------------
# test_total_timeout
# ---------------------------------------------------------------------------

def test_total_timeout():
    """超过总超时，期望 TotalTimeoutExceeded"""
    guard = AgentGuard({"total_timeout": 0.01})
    guard.reset()
    time.sleep(0.05)

    with pytest.raises(TotalTimeoutExceeded):
        guard.check_before_step()


# ---------------------------------------------------------------------------
# test_reset
# ---------------------------------------------------------------------------

def test_reset():
    """reset 后计数器归零"""
    guard = AgentGuard()
    guard.step_count = 10
    guard.call_history = [("a", "b")] * 5
    guard.start_time = 0.0

    guard.reset()

    assert guard.step_count == 0
    assert guard.call_history == []
    assert guard.start_time is not None  # 重置为当前时间
