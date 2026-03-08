"""Tests for agent/hooks.py"""

import asyncio
import os
import time

import pytest
import yaml

from agent.hooks import HookManager


@pytest.fixture
def hooks_yaml(tmp_path):
    """创建临时 hooks.yaml 并返回路径"""
    config = {
        "hooks": {
            "on_alert_received": [
                {
                    "condition": "severity == 'critical'",
                    "action": "push_websocket",
                    "params": {"channel": "critical_alerts"},
                }
            ],
            "on_decision_made": [
                {
                    "condition": "risk_level >= 'high'",
                    "action": "send_webhook",
                    "params": {"url": "http://example.com/hook"},
                },
                {
                    "condition": "always",
                    "action": "push_websocket",
                    "params": {"channel": "decisions"},
                },
            ],
            "on_error": [
                {"condition": "always", "action": "log_error"},
                {
                    "condition": "consecutive_errors >= 3",
                    "action": "send_email",
                    "params": {"to": "admin@test.com", "subject": "告警"},
                },
            ],
            "on_loop_finished": [{"condition": "always", "action": "log_info"}],
        }
    }
    yaml_path = tmp_path / "hooks.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    return str(yaml_path)


@pytest.fixture
def manager(hooks_yaml):
    return HookManager(config_path=hooks_yaml)


class TestEvaluateCondition:
    def test_always(self, manager):
        assert manager.evaluate_condition("always", {}) is True

    def test_eq_match(self, manager):
        assert manager.evaluate_condition(
            "severity == 'critical'", {"severity": "critical"}
        )

    def test_eq_no_match(self, manager):
        assert not manager.evaluate_condition(
            "severity == 'critical'", {"severity": "warning"}
        )

    def test_gte_severity(self, manager):
        assert manager.evaluate_condition(
            "risk_level >= 'high'", {"risk_level": "high"}
        )
        assert manager.evaluate_condition(
            "risk_level >= 'high'", {"risk_level": "critical"}
        )
        assert not manager.evaluate_condition(
            "risk_level >= 'high'", {"risk_level": "medium"}
        )

    def test_gte_numeric(self, manager):
        assert manager.evaluate_condition(
            "consecutive_errors >= 3", {"consecutive_errors": 3}
        )
        assert manager.evaluate_condition(
            "consecutive_errors >= 3", {"consecutive_errors": 5}
        )
        assert not manager.evaluate_condition(
            "consecutive_errors >= 3", {"consecutive_errors": 2}
        )

    def test_missing_key(self, manager):
        assert not manager.evaluate_condition(
            "severity == 'critical'", {}
        )

    def test_invalid_condition(self, manager):
        assert not manager.evaluate_condition("???", {})

    def test_string_numeric_type_mismatch_returns_false(self, manager):
        """字符串数字与真实数值比较时不应抛异常"""
        assert not manager.evaluate_condition(
            "consecutive_errors >= 3", {"consecutive_errors": "3"}
        )

    def test_float_numeric_comparison(self, manager):
        """浮点数阈值应按数值比较，而不是字符串比较"""
        assert manager.evaluate_condition("confidence >= 0.8", {"confidence": 0.85})
        assert not manager.evaluate_condition("confidence >= 0.8", {"confidence": 0.79})


class TestTrigger:
    def test_critical_alert_triggers_hook(self, manager):
        """severity=critical 时 on_alert_received 触发"""
        triggered = []
        original = manager._action_push_websocket

        def capture(params, context):
            triggered.append(("push_websocket", params, context))
            original(params, context)

        manager._action_push_websocket = capture

        asyncio.get_event_loop().run_until_complete(
            manager.trigger("on_alert_received", {"severity": "critical"})
        )
        assert len(triggered) == 1
        assert triggered[0][1]["channel"] == "critical_alerts"

    def test_condition_not_met_skips(self, manager):
        """severity=warning 不触发 critical 条件的 hook"""
        triggered = []

        def capture(params, context):
            triggered.append(True)

        manager._action_push_websocket = capture

        asyncio.get_event_loop().run_until_complete(
            manager.trigger("on_alert_received", {"severity": "warning"})
        )
        assert len(triggered) == 0

    def test_always_condition(self, manager):
        """'always' 条件始终触发"""
        triggered = []

        def capture(params, context):
            triggered.append(True)

        manager._action_log_info = capture

        asyncio.get_event_loop().run_until_complete(
            manager.trigger("on_loop_finished", {})
        )
        assert len(triggered) == 1

    def test_hook_failure_no_block(self, manager):
        """hook action 抛异常不影响返回"""

        def failing_action(params, context):
            raise RuntimeError("boom")

        manager._action_log_error = failing_action

        # on_error 有两个 hook，第一个 always+log_error 会失败，
        # 不应影响整体流程
        asyncio.get_event_loop().run_until_complete(
            manager.trigger("on_error", {"consecutive_errors": 1})
        )
        # 没有抛异常即为成功

    def test_unknown_event_no_error(self, manager):
        """触发未配置的事件名不报错"""
        asyncio.get_event_loop().run_until_complete(
            manager.trigger("on_nonexistent_event", {"foo": "bar"})
        )

    def test_unknown_action_is_ignored(self, hooks_yaml):
        """配置中存在未知 action 时，trigger 应忽略而不是中断"""
        with open(hooks_yaml, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        config["hooks"]["on_alert_received"].append(
            {"condition": "always", "action": "totally_unknown_action"}
        )

        with open(hooks_yaml, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)

        manager = HookManager(config_path=hooks_yaml)
        asyncio.get_event_loop().run_until_complete(
            manager.trigger("on_alert_received", {"severity": "critical"})
        )
        assert len(manager.get_hooks("on_alert_received")) == 2

    def test_config_hot_reload(self, hooks_yaml, manager):
        """修改 yaml 后重新触发，新配置生效"""
        # 确认当前 on_loop_finished 有 1 个 hook
        assert len(manager.get_hooks("on_loop_finished")) == 1

        # 修改配置：给 on_loop_finished 添加第二个 hook
        with open(hooks_yaml, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        config["hooks"]["on_loop_finished"].append(
            {"condition": "always", "action": "log_error"}
        )

        # 等一小会确保 mtime 变化
        time.sleep(0.05)
        with open(hooks_yaml, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)

        # 触发 — 应该自动加载新配置
        assert len(manager.get_hooks("on_loop_finished")) == 2


class TestEvaluateConditionOperators:
    """测试各种条件运算符"""

    def test_not_equal(self, manager):
        assert manager.evaluate_condition(
            "status != 'ok'", {"status": "error"}
        )
        assert not manager.evaluate_condition(
            "status != 'ok'", {"status": "ok"}
        )

    def test_less_than(self, manager):
        assert manager.evaluate_condition("count < 5", {"count": 3})
        assert not manager.evaluate_condition("count < 5", {"count": 5})

    def test_greater_than(self, manager):
        assert manager.evaluate_condition("count > 5", {"count": 6})
        assert not manager.evaluate_condition("count > 5", {"count": 5})

    def test_less_equal(self, manager):
        assert manager.evaluate_condition("count <= 5", {"count": 5})
        assert manager.evaluate_condition("count <= 5", {"count": 4})
        assert not manager.evaluate_condition("count <= 5", {"count": 6})
