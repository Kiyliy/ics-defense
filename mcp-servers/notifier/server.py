import json
import logging
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="notifier", instructions="ICS 安全消息通知服务")
logger = logging.getLogger("notifier")

# 通知记录（内存）
notification_log = []

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
    # 实际环境用 httpx/requests 发送 POST 请求
    # 当前实现只记录日志
    record = {
        "channel": "webhook",
        "url": url,
        "message": message,
        "level": level,
        "status": "sent",
        "timestamp": datetime.now().isoformat()
    }
    notification_log.append(record)
    logger.info(f"Webhook [{level}]: {message[:100]}")
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
    record = {
        "channel": "email",
        "to": to,
        "subject": subject,
        "body": body,
        "status": "sent",
        "timestamp": datetime.now().isoformat()
    }
    notification_log.append(record)
    logger.info(f"Email to {to}: {subject}")
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
    record = {
        "channel": f"ws:{channel}",
        "message": message,
        "data": data,
        "status": "pushed",
        "timestamp": datetime.now().isoformat()
    }
    notification_log.append(record)
    logger.info(f"WebSocket [{channel}]: {message[:100]}")
    return json.dumps(record, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run()
