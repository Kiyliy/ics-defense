"""通知管理器。

统一管理多个通知渠道，提供高层级的通知发送接口。
"""

import logging
import os
from typing import Any, Optional

from .channels.email import EmailChannel
from .channels.feishu import FeishuChannel
from .channels.webhook import WebhookChannel
from .templates.alert_card import (
    format_alert_notification,
    format_approval_notification,
    format_decision_notification,
    format_error_notification,
)

logger = logging.getLogger(__name__)

# 事件类型 -> 模板格式化函数 的映射
_EVENT_FORMATTERS: dict[str, Any] = {
    "alert": format_alert_notification,
    "decision": format_decision_notification,
    "approval": format_approval_notification,
    "error": format_error_notification,
}

# 事件类型 -> 默认严重等级
_EVENT_DEFAULT_LEVELS: dict[str, str] = {
    "alert": "medium",
    "decision": "info",
    "approval": "medium",
    "error": "high",
}


class NotificationManager:
    """通知管理器。

    从环境变量或配置字典加载渠道配置，管理多个通知渠道，
    并提供统一的通知发送接口。单个渠道失败不影响其他渠道。

    用法::

        manager = NotificationManager.from_env()
        await manager.notify("alert", {"alert_type": "入侵检测", ...})

    Args:
        config: 渠道配置字典，格式如下::

            {
                "feishu": {"webhook_url": "...", "secret": "", ...},
                "webhook": {"url": "...", "headers": {}, "timeout": 10},
                "email": {"smtp_host": "...", ...},
            }
    """

    def __init__(self, config: Optional[dict[str, dict]] = None) -> None:
        self._channels: dict[str, Any] = {}
        if config:
            self._init_channels(config)

    # ------------------------------------------------------------------
    # 工厂方法
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "NotificationManager":
        """从环境变量创建通知管理器。

        读取以下环境变量:
            - FEISHU_BOT_WEBHOOK_URL: 飞书 Webhook 地址。
            - FEISHU_BOT_SECRET: 飞书签名密钥。
            - FEISHU_APP_ID / FEISHU_APP_SECRET: 飞书应用凭据。
            - FEISHU_APP_RECEIVE_ID: 飞书消息接收者。
            - FEISHU_APP_RECEIVE_ID_TYPE: 接收者 ID 类型。
            - WEBHOOK_NOTIFICATION_URL: 通用 Webhook 地址。
            - WEBHOOK_NOTIFICATION_HEADERS: 自定义请求头（JSON）。
            - SMTP_HOST / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD: 邮件配置。
            - SMTP_FROM_ADDR / SMTP_TO_ADDRS: 邮件收发地址。

        Returns:
            已配置的 NotificationManager 实例。
        """
        config: dict[str, dict] = {}

        # ---- 飞书 ----
        feishu_webhook = os.getenv("FEISHU_BOT_WEBHOOK_URL", "")
        feishu_app_id = os.getenv("FEISHU_APP_ID", "")
        if feishu_webhook or feishu_app_id:
            config["feishu"] = {
                "webhook_url": feishu_webhook,
                "secret": os.getenv("FEISHU_BOT_SECRET", ""),
                "app_id": feishu_app_id,
                "app_secret": os.getenv("FEISHU_APP_SECRET", ""),
                "receive_id": os.getenv("FEISHU_APP_RECEIVE_ID", ""),
                "receive_id_type": os.getenv("FEISHU_APP_RECEIVE_ID_TYPE", "chat_id"),
            }

        # ---- 通用 Webhook ----
        webhook_url = os.getenv("WEBHOOK_NOTIFICATION_URL", "")
        if webhook_url:
            import json as _json

            headers_str = os.getenv("WEBHOOK_NOTIFICATION_HEADERS", "{}")
            try:
                headers = _json.loads(headers_str)
            except _json.JSONDecodeError:
                headers = {}
            config["webhook"] = {
                "url": webhook_url,
                "headers": headers,
                "timeout": int(os.getenv("WEBHOOK_NOTIFICATION_TIMEOUT", "10")),
            }

        # ---- 邮件 ----
        smtp_host = os.getenv("SMTP_HOST", "")
        if smtp_host:
            to_addrs_str = os.getenv("SMTP_TO_ADDRS", "")
            to_addrs = [a.strip() for a in to_addrs_str.split(",") if a.strip()]
            config["email"] = {
                "smtp_host": smtp_host,
                "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                "username": os.getenv("SMTP_USERNAME", ""),
                "password": os.getenv("SMTP_PASSWORD", ""),
                "from_addr": os.getenv("SMTP_FROM_ADDR", ""),
                "to_addrs": to_addrs,
                "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
            }

        instance = cls(config)
        configured = [name for name, ch in instance._channels.items() if ch.is_configured()]
        logger.info("通知管理器已初始化，已配置渠道: %s", configured or "无")
        return instance

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _init_channels(self, config: dict[str, dict]) -> None:
        """根据配置字典初始化各渠道实例。"""
        if "feishu" in config:
            self._channels["feishu"] = FeishuChannel(**config["feishu"])

        if "webhook" in config:
            self._channels["webhook"] = WebhookChannel(**config["webhook"])

        if "email" in config:
            self._channels["email"] = EmailChannel(**config["email"])

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_configured_channels(self) -> list[str]:
        """返回已配置的渠道名称列表。"""
        return [name for name, ch in self._channels.items() if ch.is_configured()]

    async def notify(
        self,
        event_type: str,
        data: dict,
        channels: Optional[list[str]] = None,
    ) -> dict[str, bool]:
        """发送通知到指定渠道。

        根据事件类型自动选择模板格式化消息，然后发送到指定（或所有已配置）渠道。
        单个渠道失败不影响其他渠道的发送。

        Args:
            event_type: 事件类型，可选: "alert", "decision", "approval", "error"。
                如果不在预定义类型中，将直接使用 data 中的 title/content。
            data: 事件数据字典，传递给模板格式化函数。
            channels: 指定发送渠道名称列表。为 None 时发送到所有已配置渠道。

        Returns:
            各渠道发送结果，如 {"feishu": True, "email": False}。
        """
        # 格式化消息
        formatter = _EVENT_FORMATTERS.get(event_type)
        if formatter:
            title, content = formatter(data)
        else:
            title = data.get("title", f"通知: {event_type}")
            content = data.get("content", "")

        level = data.get("level", _EVENT_DEFAULT_LEVELS.get(event_type, "info"))
        metadata = data.get("metadata")

        # 确定目标渠道
        if channels:
            target_channels = {
                name: ch
                for name, ch in self._channels.items()
                if name in channels and ch.is_configured()
            }
        else:
            target_channels = {
                name: ch
                for name, ch in self._channels.items()
                if ch.is_configured()
            }

        if not target_channels:
            logger.warning("没有可用的通知渠道，事件 '%s' 未发送", event_type)
            return {}

        # 逐一发送，捕获每个渠道的异常
        results: dict[str, bool] = {}
        for name, channel in target_channels.items():
            try:
                logger.info("正在通过 '%s' 渠道发送通知: %s", name, title)
                success = await channel.send(
                    title=title,
                    content=content,
                    level=level,
                    metadata=metadata,
                )
                results[name] = success
                if success:
                    logger.info("渠道 '%s' 发送成功", name)
                else:
                    logger.warning("渠道 '%s' 发送失败", name)
            except Exception as exc:
                logger.error("渠道 '%s' 发送异常: %s", name, exc)
                results[name] = False

        return results
