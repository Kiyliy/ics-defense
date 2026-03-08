"""Agent 安全守卫模块 - 防止循环卡死、工具调用失败"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, Callable, Coroutine


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class GuardException(Exception):
    """Guard 异常基类"""


class MaxStepsExceeded(GuardException):
    """超过最大步数"""


class TotalTimeoutExceeded(GuardException):
    """超过总超时时间"""


class AgentStuck(GuardException):
    """Agent 陷入死循环"""


# ---------------------------------------------------------------------------
# AgentGuard
# ---------------------------------------------------------------------------

class AgentGuard:
    """Agent 安全守卫"""

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.max_steps: int = cfg.get("max_steps", 20)
        self.max_retries: int = cfg.get("max_retries", 2)
        self.step_timeout: int | float = cfg.get("step_timeout", 30)
        self.total_timeout: int | float = cfg.get("total_timeout", 300)
        self.stuck_threshold: int = cfg.get("stuck_threshold", 3)

        self.step_count: int = 0
        self.call_history: list[tuple[str, str]] = []
        self.start_time: float | None = None

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """重置计数器，开始新的分析"""
        self.step_count = 0
        self.call_history = []
        self.start_time = time.monotonic()

    # ------------------------------------------------------------------
    def check_before_step(self) -> None:
        """每步前检查：max_steps + total_timeout"""
        if self.start_time is None:
            self.start_time = time.monotonic()

        if self.step_count >= self.max_steps:
            raise MaxStepsExceeded(
                f"已达到最大步数限制 ({self.max_steps})"
            )

        elapsed = time.monotonic() - self.start_time
        if elapsed > self.total_timeout:
            raise TotalTimeoutExceeded(
                f"已超过总超时时间 ({self.total_timeout}s)，已用 {elapsed:.1f}s"
            )

    # ------------------------------------------------------------------
    def check_stuck(self, tool_name: str, args: Any) -> None:
        """检测死循环：连续 N 次相同工具 + 相同参数"""
        args_hash = hashlib.md5(
            json.dumps(args, sort_keys=True, default=str).encode()
        ).hexdigest()
        key = (tool_name, args_hash)
        self.call_history.append(key)

        if len(self.call_history) >= self.stuck_threshold:
            recent = self.call_history[-self.stuck_threshold:]
            if all(k == recent[0] for k in recent):
                raise AgentStuck(
                    f"连续 {self.stuck_threshold} 次相同调用: "
                    f"tool={tool_name}"
                )

    # ------------------------------------------------------------------
    async def execute_with_retry(
        self,
        tool_call_fn: Callable[..., Coroutine[Any, Any, Any]],
        tool_name: str,
        args: Any,
    ) -> Any:
        """带重试和超时的工具调用"""
        self.step_count += 1
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    tool_call_fn(tool_name, args),
                    timeout=self.step_timeout,
                )
                return result
            except asyncio.TimeoutError:
                last_error = TimeoutError(
                    f"{tool_name} 第 {attempt + 1} 次调用超时 "
                    f"(>{self.step_timeout}s)"
                )
            except ConnectionError as exc:
                last_error = exc

        # 所有重试都失败 — 返回 error dict 而非抛异常
        return {"error": f"工具 {tool_name} 调用失败: {last_error}"}
