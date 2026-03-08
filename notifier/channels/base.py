"""通知渠道抽象基类。

定义所有通知渠道必须实现的接口。
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseNotificationChannel(ABC):
    """通知渠道抽象基类。

    所有具体的通知渠道（飞书、邮件、Webhook 等）都必须继承此类，
    并实现 send 和 is_configured 方法。
    """

    @abstractmethod
    async def send(
        self,
        title: str,
        content: str,
        level: str = "info",
        metadata: Optional[dict] = None,
    ) -> bool:
        """发送通知消息。

        Args:
            title: 通知标题。
            content: 通知正文内容，可包含 Markdown 格式。
            level: 严重等级，可选值: "critical", "high", "medium", "low", "info"。
            metadata: 附加元数据，由具体渠道决定如何使用。

        Returns:
            发送成功返回 True，否则返回 False。
        """
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """检查该渠道是否已正确配置。

        Returns:
            配置完整返回 True，否则返回 False。
        """
        ...
