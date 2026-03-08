"""通用 Webhook 通知渠道。

向可配置的 URL 发送 JSON 格式的通知消息。
"""

import logging
import time
from typing import Any, Optional

import httpx

from .base import BaseNotificationChannel

logger = logging.getLogger(__name__)


class WebhookChannel(BaseNotificationChannel):
    """通用 Webhook 通知渠道。

    以 POST 方式将通知内容序列化为 JSON 发送到目标 URL。

    Args:
        url: 目标 Webhook 地址。
        headers: 自定义请求头。
        timeout: 请求超时时间（秒），默认 10。
    """

    def __init__(
        self,
        url: str = "",
        headers: Optional[dict[str, str]] = None,
        timeout: int = 10,
    ) -> None:
        self.url = url.strip()
        self.headers = headers or {}
        self.timeout = timeout

    def is_configured(self) -> bool:
        """检查 Webhook 渠道是否已配置。"""
        return bool(self.url)

    async def send(
        self,
        title: str,
        content: str,
        level: str = "info",
        metadata: Optional[dict] = None,
    ) -> bool:
        """通过 Webhook 发送通知。

        请求体格式::

            {
                "title": "...",
                "content": "...",
                "level": "...",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {...}
            }

        Args:
            title: 通知标题。
            content: 通知正文。
            level: 严重等级。
            metadata: 附加元数据。

        Returns:
            发送成功返回 True。
        """
        if not self.is_configured():
            logger.warning("Webhook 渠道未配置，跳过发送")
            return False

        payload: dict[str, Any] = {
            "title": title,
            "content": content,
            "level": level,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "metadata": metadata or {},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.url,
                    json=payload,
                    headers=self.headers,
                )
                resp.raise_for_status()

            logger.info("Webhook 发送成功: %s -> %s", title, self.url)
            return True

        except httpx.HTTPStatusError as exc:
            logger.error("Webhook HTTP 错误: %s", exc)
            return False
        except Exception as exc:
            logger.error("Webhook 发送异常: %s", exc)
            return False
