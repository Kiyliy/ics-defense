import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-servers'))

from notifier.server import send_webhook, send_email, push_websocket, notification_log


@pytest.fixture(autouse=True)
def clear_log():
    notification_log.clear()
    yield
    notification_log.clear()


def test_send_webhook():
    """发送 webhook -> status=sent, channel=webhook"""
    result = json.loads(send_webhook(
        url="https://hooks.example.com/webhook",
        message="检测到异常流量"
    ))
    assert result["status"] == "sent"
    assert result["channel"] == "webhook"
    assert "timestamp" in result


def test_send_email():
    """发送邮件 -> status=sent, channel=email, to 正确"""
    result = json.loads(send_email(
        to="admin@example.com",
        subject="安全告警",
        body="发现可疑连接"
    ))
    assert result["status"] == "sent"
    assert result["channel"] == "email"
    assert result["to"] == "admin@example.com"
    assert "timestamp" in result


def test_push_websocket():
    """推送 ws -> status=pushed, channel 包含频道名"""
    result = json.loads(push_websocket(
        channel="critical_alerts",
        message="紧急告警"
    ))
    assert result["status"] == "pushed"
    assert "critical_alerts" in result["channel"]
    assert "timestamp" in result


def test_notification_log_recorded():
    """发送后 notification_log 有记录"""
    assert len(notification_log) == 0
    send_webhook(url="https://hooks.example.com/webhook", message="test1")
    send_email(to="a@b.com", subject="s", body="b")
    push_websocket(channel="decisions", message="test2")
    assert len(notification_log) == 3


def test_send_webhook_with_level():
    """level=critical 正确记录"""
    result = json.loads(send_webhook(
        url="https://hooks.example.com/webhook",
        message="严重告警",
        level="critical"
    ))
    assert result["level"] == "critical"
    assert notification_log[-1]["level"] == "critical"


def test_push_websocket_with_data():
    """附加 data JSON 正确传递"""
    extra = json.dumps({"alert_id": "a-001", "severity": "high"})
    result = json.loads(push_websocket(
        channel="approvals",
        message="需要审批",
        data=extra
    ))
    assert result["data"] == extra
    assert notification_log[-1]["data"] == extra
