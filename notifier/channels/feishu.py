"""飞书（Lark/Feishu）通知渠道。

支持两种发送模式：
1. Bot Webhook —— 简单模式，向 Webhook URL 发送卡片消息。
2. App API —— 高级模式，使用 app_id/app_secret 获取 tenant_access_token 后发送消息。
"""

import base64
import hashlib
import hmac
import logging
import time
from typing import Optional

import httpx

from .base import BaseNotificationChannel

logger = logging.getLogger(__name__)

# 严重等级 -> 飞书卡片颜色模板
_LEVEL_COLORS: dict[str, str] = {
    "critical": "red",
    "high": "orange",
    "medium": "yellow",
    "low": "green",
    "info": "blue",
}

# 严重等级 -> 中文标签
_LEVEL_LABELS: dict[str, str] = {
    "critical": "严重",
    "high": "高危",
    "medium": "中等",
    "low": "低危",
    "info": "信息",
}


def _generate_sign(secret: str, timestamp: str) -> str:
    """生成飞书 Bot Webhook 签名。

    Args:
        secret: 签名密钥。
        timestamp: Unix 时间戳字符串。

    Returns:
        Base64 编码的签名字符串。
    """
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def _build_card_message(
    title: str,
    content: str,
    level: str = "info",
    metadata: Optional[dict] = None,
) -> dict:
    """构建飞书交互卡片消息体。

    Args:
        title: 卡片标题。
        content: 卡片正文（支持 Markdown）。
        level: 严重等级。
        metadata: 附加元数据，将以字段形式展示。

    Returns:
        飞书消息卡片 JSON 结构。
    """
    color = _LEVEL_COLORS.get(level, "blue")
    label = _LEVEL_LABELS.get(level, "信息")

    elements: list[dict] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": content,
            },
        },
        {"tag": "hr"},
        {
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"等级: {label} | 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                }
            ],
        },
    ]

    # 如果有元数据，插入字段区域
    if metadata:
        fields = []
        for key, value in metadata.items():
            fields.append(
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{key}:** {value}",
                    },
                }
            )
        elements.insert(1, {"tag": "div", "fields": fields})

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": title,
            },
            "template": color,
        },
        "elements": elements,
    }

    return card


class FeishuChannel(BaseNotificationChannel):
    """飞书通知渠道。

    优先使用 Bot Webhook 模式；当配置了 app_id 和 app_secret 时，
    同时支持 App API 模式发送消息到指定会话。

    Args:
        webhook_url: Bot Webhook 地址。
        secret: Webhook 签名密钥（可选）。
        app_id: 飞书应用 ID（App API 模式）。
        app_secret: 飞书应用密钥（App API 模式）。
        receive_id: 消息接收者 ID（App API 模式）。
        receive_id_type: 接收者 ID 类型，默认 "chat_id"。
    """

    # tenant_access_token 缓存
    _token: Optional[str] = None
    _token_expires_at: float = 0.0

    def __init__(
        self,
        webhook_url: str = "",
        secret: str = "",
        app_id: str = "",
        app_secret: str = "",
        receive_id: str = "",
        receive_id_type: str = "chat_id",
    ) -> None:
        self.webhook_url = webhook_url.strip()
        self.secret = secret.strip()
        self.app_id = app_id.strip()
        self.app_secret = app_secret.strip()
        self.receive_id = receive_id.strip()
        self.receive_id_type = receive_id_type.strip() or "chat_id"

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """检查飞书渠道是否已配置。

        Webhook URL 或 App API 凭据至少需要配置一种。
        """
        has_webhook = bool(self.webhook_url)
        has_app = bool(self.app_id and self.app_secret and self.receive_id)
        return has_webhook or has_app

    async def send(
        self,
        title: str,
        content: str,
        level: str = "info",
        metadata: Optional[dict] = None,
    ) -> bool:
        """通过飞书发送通知。

        优先使用 Webhook 模式；如果 Webhook 未配置但 App API 已配置，
        则使用 App API 模式。

        Args:
            title: 通知标题。
            content: 通知正文。
            level: 严重等级。
            metadata: 附加元数据。

        Returns:
            发送成功返回 True。
        """
        if self.webhook_url:
            return await self._send_via_webhook(title, content, level, metadata)

        if self.app_id and self.app_secret and self.receive_id:
            return await self._send_via_app_api(title, content, level, metadata)

        logger.warning("飞书渠道未配置，跳过发送")
        return False

    # ------------------------------------------------------------------
    # Bot Webhook 模式
    # ------------------------------------------------------------------

    async def _send_via_webhook(
        self,
        title: str,
        content: str,
        level: str,
        metadata: Optional[dict],
    ) -> bool:
        """通过 Bot Webhook 发送卡片消息。"""
        card = _build_card_message(title, content, level, metadata)
        payload: dict = {
            "msg_type": "interactive",
            "card": card,
        }

        # 签名验证
        if self.secret:
            timestamp = str(int(time.time()))
            sign = _generate_sign(self.secret, timestamp)
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
                result = resp.json()

                if result.get("code", -1) != 0:
                    logger.error(
                        "飞书 Webhook 返回错误: code=%s, msg=%s",
                        result.get("code"),
                        result.get("msg"),
                    )
                    return False

                logger.info("飞书 Webhook 发送成功: %s", title)
                return True

        except httpx.HTTPStatusError as exc:
            logger.error("飞书 Webhook HTTP 错误: %s", exc)
            return False
        except Exception as exc:
            logger.error("飞书 Webhook 发送异常: %s", exc)
            return False

    # ------------------------------------------------------------------
    # App API 模式
    # ------------------------------------------------------------------

    async def _get_tenant_access_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """获取或刷新 tenant_access_token。

        使用内部缓存，避免频繁请求。令牌有效期内直接返回缓存值。
        """
        if self._token and time.time() < self._token_expires_at:
            return self._token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }

        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code", -1) != 0:
                logger.error("获取 tenant_access_token 失败: %s", data.get("msg"))
                return None

            self._token = data.get("tenant_access_token")
            # 提前 5 分钟过期以留出余量
            expire = data.get("expire", 7200)
            self._token_expires_at = time.time() + expire - 300
            return self._token

        except Exception as exc:
            logger.error("获取 tenant_access_token 异常: %s", exc)
            return None

    async def _send_via_app_api(
        self,
        title: str,
        content: str,
        level: str,
        metadata: Optional[dict],
    ) -> bool:
        """通过 App API 发送卡片消息到指定会话。"""
        card = _build_card_message(title, content, level, metadata)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token = await self._get_tenant_access_token(client)
                if not token:
                    return False

                url = (
                    f"https://open.feishu.cn/open-apis/im/v1/messages"
                    f"?receive_id_type={self.receive_id_type}"
                )
                headers = {"Authorization": f"Bearer {token}"}

                import json as _json

                payload = {
                    "receive_id": self.receive_id,
                    "msg_type": "interactive",
                    "content": _json.dumps(card),
                }

                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                result = resp.json()

                if result.get("code", -1) != 0:
                    logger.error(
                        "飞书 App API 返回错误: code=%s, msg=%s",
                        result.get("code"),
                        result.get("msg"),
                    )
                    return False

                logger.info("飞书 App API 发送成功: %s", title)
                return True

        except httpx.HTTPStatusError as exc:
            logger.error("飞书 App API HTTP 错误: %s", exc)
            return False
        except Exception as exc:
            logger.error("飞书 App API 发送异常: %s", exc)
            return False
