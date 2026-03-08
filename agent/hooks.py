"""
事件钩子管理器 — 在 Agent 生命周期关键节点触发动作。
"""

import os
import re
import logging
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 支持的事件名称
HOOK_EVENTS = [
    "on_alert_received",
    "on_plan_generated",
    "on_tool_called",
    "on_tool_result",
    "on_approval_needed",
    "on_decision_made",
    "on_error",
    "on_loop_finished",
]

# 用于有序比较的级别映射
_SEVERITY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class HookManager:
    """事件钩子管理器，基于 YAML 配置"""

    def __init__(self, config_path: str = "agent/hooks.yaml"):
        self.config_path = config_path
        self.hooks: dict[str, list[dict]] = {}
        self._load_config()
        try:
            self._last_modified = os.path.getmtime(config_path)
        except OSError:
            self._last_modified = 0

    # ------------------------------------------------------------------ #
    #  配置加载
    # ------------------------------------------------------------------ #

    def _load_config(self):
        """加载 hooks.yaml"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.hooks = data.get("hooks", {})
        except FileNotFoundError:
            logger.warning("hooks 配置文件不存在: %s", self.config_path)
            self.hooks = {}
        except Exception as exc:
            logger.error("加载 hooks 配置失败: %s", exc)
            self.hooks = {}

    def _check_reload(self):
        """检查文件是否修改，自动热加载"""
        try:
            mtime = os.path.getmtime(self.config_path)
        except OSError:
            return
        if mtime != self._last_modified:
            logger.info("检测到 hooks 配置变更，热加载中...")
            self._load_config()
            self._last_modified = mtime

    # ------------------------------------------------------------------ #
    #  条件求值（不使用 eval，安全解析）
    # ------------------------------------------------------------------ #

    def evaluate_condition(self, condition: str, context: dict) -> bool:
        """评估条件表达式。

        支持格式:
        - "always"                          → True
        - "severity == 'critical'"          → context["severity"] == "critical"
        - "risk_level >= 'high'"            → 按级别比较
        - "consecutive_errors >= 3"         → 数值比较
        """
        condition = condition.strip()

        if condition == "always":
            return True

        # 匹配: key op 'string' 或 key op number
        pattern = r"^(\w+)\s*(==|!=|>=|<=|>|<)\s*(.+)$"
        m = re.match(pattern, condition)
        if not m:
            logger.warning("无法解析条件表达式: %s", condition)
            return False

        key, op, raw_value = m.group(1), m.group(2), m.group(3).strip()

        # 解析右侧值
        if (raw_value.startswith("'") and raw_value.endswith("'")) or (
            raw_value.startswith('"') and raw_value.endswith('"')
        ):
            value: Any = raw_value[1:-1]
        else:
            try:
                value = int(raw_value)
            except ValueError:
                try:
                    value = float(raw_value)
                except ValueError:
                    value = raw_value

        ctx_value = context.get(key)
        if ctx_value is None:
            return False

        # 如果双方都在级别映射中，按级别比较
        if (
            isinstance(value, str)
            and value in _SEVERITY_ORDER
            and isinstance(ctx_value, str)
            and ctx_value in _SEVERITY_ORDER
        ):
            left = _SEVERITY_ORDER[ctx_value]
            right = _SEVERITY_ORDER[value]
        else:
            left = ctx_value
            right = value

        try:
            if op == "==":
                return left == right
            elif op == "!=":
                return left != right
            elif op == ">=":
                return left >= right
            elif op == "<=":
                return left <= right
            elif op == ">":
                return left > right
            elif op == "<":
                return left < right
        except TypeError:
            return False

        return False

    # ------------------------------------------------------------------ #
    #  Action handlers（stub 实现）
    # ------------------------------------------------------------------ #

    def _action_log_error(self, params: dict, context: dict):
        logger.error("[hook:log_error] %s", context)

    def _action_log_info(self, params: dict, context: dict):
        logger.info("[hook:log_info] %s", context)

    def _action_push_websocket(self, params: dict, context: dict):
        channel = params.get("channel", "default")
        logger.info("[hook:push_websocket] channel=%s context=%s", channel, context)

    def _action_send_webhook(self, params: dict, context: dict):
        url = params.get("url", "")
        logger.info("[hook:send_webhook] url=%s context=%s", url, context)

    def _action_send_email(self, params: dict, context: dict):
        to = params.get("to", "")
        subject = params.get("subject", "")
        logger.info("[hook:send_email] to=%s subject=%s", to, subject)

    _ACTION_HANDLERS = {
        "log_error": "_action_log_error",
        "log_info": "_action_log_info",
        "push_websocket": "_action_push_websocket",
        "send_webhook": "_action_send_webhook",
        "send_email": "_action_send_email",
    }

    # ------------------------------------------------------------------ #
    #  触发
    # ------------------------------------------------------------------ #

    async def trigger(self, event_name: str, context: dict):
        """触发指定事件的所有钩子。

        hook 执行失败不阻塞 Agent 主流程。
        """
        self._check_reload()

        hooks = self.hooks.get(event_name, [])
        for hook_cfg in hooks:
            try:
                condition = hook_cfg.get("condition", "always")
                if not self.evaluate_condition(condition, context):
                    continue

                action = hook_cfg.get("action", "")
                params = hook_cfg.get("params", {})
                handler_name = self._ACTION_HANDLERS.get(action)

                if handler_name is None:
                    logger.warning("未知的 hook action: %s", action)
                    continue

                handler = getattr(self, handler_name)
                handler(params, context)
                logger.debug(
                    "hook 已触发: event=%s action=%s", event_name, action
                )
            except Exception as exc:
                logger.error(
                    "hook 执行失败（已忽略）: event=%s error=%s",
                    event_name,
                    exc,
                )

    def get_hooks(self, event_name: str) -> list:
        """获取某事件的所有钩子配置"""
        self._check_reload()
        return self.hooks.get(event_name, [])
