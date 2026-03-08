"""工具权限策略管理模块"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class ToolPolicy:
    """工具权限策略管理"""

    VALID_LEVELS = ("auto", "notify", "approve")

    def __init__(self, config_path: str = "agent/tool_policy.yaml"):
        self._config_path = self._resolve_path(config_path)
        self._tool_map: dict[str, str] = {}
        self._raw_config: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_path(config_path: str) -> Path:
        """将相对路径解析为基于项目根目录的绝对路径"""
        p = Path(config_path)
        if not p.is_absolute():
            # 相对于本文件所在包的上级目录（即项目根）
            base = Path(__file__).resolve().parent.parent
            p = base / config_path
        return p

    # ------------------------------------------------------------------
    def _load(self) -> None:
        with open(self._config_path, "r", encoding="utf-8") as fh:
            self._raw_config = yaml.safe_load(fh) or {}

        self._tool_map = {}
        tool_levels: dict[str, list[str]] = self._raw_config.get("tool_levels", {})
        for level, tools in tool_levels.items():
            if level not in self.VALID_LEVELS:
                continue
            for tool_name in tools:
                self._tool_map[tool_name] = level

    # ------------------------------------------------------------------
    def get_level(self, tool_name: str) -> str:
        """返回工具权限等级: 'auto' | 'notify' | 'approve'

        未知工具默认 'approve'（安全第一）。
        """
        return self._tool_map.get(tool_name, "approve")

    # ------------------------------------------------------------------
    def reload(self) -> None:
        """热加载配置"""
        self._load()

    # ------------------------------------------------------------------
    @property
    def approval_timeout(self) -> int:
        """审批超时时间（秒）"""
        return int(self._raw_config.get("approval_timeout", 300))
