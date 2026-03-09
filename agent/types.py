"""Agent 共享类型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExecutionResult:
    """执行阶段的输出结果"""
    last_content: Optional[str] = None
    exec_messages: list[dict[str, Any]] = field(default_factory=list)
    terminated_by_guard: bool = False
    guard_error: Optional[str] = None


@dataclass
class Decision:
    """最终决策"""
    risk_level: str = "unknown"
    confidence: float = 0.0
    attack_chain: list[dict[str, str]] = field(default_factory=list)
    recommendation: str = ""
    action_type: str = "manual_review"
    rationale: str = ""
    trace_id: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（与原 agent_loop 返回格式兼容）"""
        d: dict[str, Any] = {
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "attack_chain": self.attack_chain,
            "recommendation": self.recommendation,
            "action_type": self.action_type,
            "rationale": self.rationale,
            "trace_id": self.trace_id,
            "token_usage": self.token_usage,
        }
        if self.error is not None:
            d["error"] = self.error
        if self.error_type is not None:
            d["error_type"] = self.error_type
        return d
