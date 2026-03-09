import json
import logging
import re
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("notifier")

mcp = FastMCP(name="notifier", instructions="ICS 安全消息通知服务")

# 通知记录（内存）
notification_log = []

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
_URL_PATTERN = re.compile(r"^https?://[^\s]+$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_LEVELS = {"info", "warning", "critical"}
_VALID_CHANNELS = {"critical_alerts", "decisions", "approvals", "alerts", "status"}


def _validate_url(url: str) -> str:
    if not url or not url.strip():
        raise ValueError("Webhook URL 不能为空")
    url = url.strip()
    if not _URL_PATTERN.match(url):
        raise ValueError(f"无效的 Webhook URL: '{url}'，需要以 http:// 或 https:// 开头")
    return url


def _validate_email(email: str) -> str:
    if not email or not email.strip():
        raise ValueError("收件人邮箱不能为空")
    email = email.strip()
    if not _EMAIL_PATTERN.match(email):
        raise ValueError(f"无效的邮箱地址: '{email}'")
    return email


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def send_webhook(url: str, message: str, level: str = "info") -> str:
    """发送 Webhook 通知（企业微信/钉钉/飞书）

    Args:
        url: Webhook URL
        message: 通知内容
        level: 通知级别 (info/warning/critical)

    Returns:
        JSON: {"status": "sent", "channel": "webhook", "timestamp": "..."}
    """
    try:
        url = _validate_url(url)
    except ValueError as exc:
        logger.warning("send_webhook URL校验失败: %s", exc)
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)

    if not message or not message.strip():
        logger.warning("send_webhook: message 为空")
        return json.dumps({"status": "error", "error": "message 不能为空"}, ensure_ascii=False)

    if level not in _VALID_LEVELS:
        logger.warning("send_webhook: 无效的 level: %s，使用默认 info", level)
        level = "info"

    # 实际环境用 httpx/requests 发送 POST 请求
    # 当前实现只记录日志
    record = {
        "channel": "webhook",
        "url": url,
        "message": message,
        "level": level,
        "status": "sent",
        "timestamp": datetime.now().isoformat(),
    }
    notification_log.append(record)
    logger.info("Webhook [%s] -> %s: %s", level, url[:60], message[:100])
    return json.dumps(record, ensure_ascii=False)


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件告警

    Args:
        to: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文

    Returns:
        JSON: {"status": "sent", "channel": "email", "to": "...", "timestamp": "..."}
    """
    try:
        to = _validate_email(to)
    except ValueError as exc:
        logger.warning("send_email 邮箱校验失败: %s", exc)
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)

    if not subject or not subject.strip():
        logger.warning("send_email: subject 为空")
        return json.dumps({"status": "error", "error": "subject 不能为空"}, ensure_ascii=False)

    if not body or not body.strip():
        logger.warning("send_email: body 为空")
        return json.dumps({"status": "error", "error": "body 不能为空"}, ensure_ascii=False)

    record = {
        "channel": "email",
        "to": to,
        "subject": subject,
        "body": body,
        "status": "sent",
        "timestamp": datetime.now().isoformat(),
    }
    notification_log.append(record)
    logger.info("Email to %s: %s", to, subject)
    return json.dumps(record, ensure_ascii=False)


@mcp.tool()
def push_websocket(channel: str, message: str, data: str = "{}") -> str:
    """WebSocket 实时推送到前端

    Args:
        channel: 推送频道 (critical_alerts/decisions/approvals)
        message: 推送消息
        data: 附加数据 JSON

    Returns:
        JSON: {"status": "pushed", "channel": "...", "timestamp": "..."}
    """
    if not channel or not channel.strip():
        logger.warning("push_websocket: channel 为空")
        return json.dumps({"status": "error", "error": "channel 不能为空"}, ensure_ascii=False)

    if not message or not message.strip():
        logger.warning("push_websocket: message 为空")
        return json.dumps({"status": "error", "error": "message 不能为空"}, ensure_ascii=False)

    # Validate data is valid JSON
    try:
        if isinstance(data, str):
            json.loads(data)
    except json.JSONDecodeError as exc:
        logger.warning("push_websocket: data JSON 无效: %s", exc)
        return json.dumps({"status": "error", "error": f"data 必须为有效 JSON: {exc}"}, ensure_ascii=False)

    record = {
        "channel": f"ws:{channel}",
        "message": message,
        "data": data,
        "status": "pushed",
        "timestamp": datetime.now().isoformat(),
    }
    notification_log.append(record)
    logger.info("WebSocket [%s]: %s", channel, message[:100])
    return json.dumps(record, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
