"""Wazuh HIDS 数据源采集器

通过 Wazuh REST API 获取告警信息，输出格式与 normalizer.normalize_hids() 对齐。
典型字段: rule.id, rule.description, rule.level, rule.groups, agent.ip, data.srcip
"""

import asyncio
import logging
from typing import AsyncIterator

import httpx

from .base import BaseCollector

logger = logging.getLogger(__name__)


class HIDSCollector(BaseCollector):
    """Wazuh HIDS 采集器，通过 REST API 轮询告警"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.source_type = "hids"
        self.url = self.config.get("url", "https://localhost:55000")
        self.user = self.config.get("user", "wazuh")
        self.password = self.config.get("password", "wazuh")
        self.poll_interval = self.config.get("poll_interval", 15)
        self._token: str | None = None
        self._last_timestamp: str | None = None

    async def health_check(self) -> bool:
        """检查 Wazuh API 是否可达"""
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.get(f"{self.url}/")
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("HIDS 健康检查失败: %s", exc)
            return False

    async def collect(self) -> AsyncIterator[dict]:
        """持续轮询 Wazuh API 获取告警"""
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            while self._running:
                try:
                    await self._ensure_token(client)

                    params: dict = {"limit": 100, "sort": "-timestamp"}
                    if self._last_timestamp:
                        params["q"] = f"timestamp>{self._last_timestamp}"

                    resp = await client.get(
                        f"{self.url}/alerts",
                        headers=self._auth_headers(),
                        params=params,
                    )

                    # Token 过期时重新认证
                    if resp.status_code == 401:
                        self._token = None
                        await self._ensure_token(client)
                        resp = await client.get(
                            f"{self.url}/alerts",
                            headers=self._auth_headers(),
                            params=params,
                        )

                    resp.raise_for_status()
                    body = resp.json()

                    items = body.get("data", {}).get("affected_items", [])
                    for alert in items:
                        ts = alert.get("timestamp")
                        if ts:
                            self._last_timestamp = ts
                        yield alert

                except httpx.HTTPStatusError as exc:
                    logger.warning("Wazuh API 错误 %s: %s", exc.response.status_code, exc)
                except httpx.RequestError as exc:
                    logger.warning("Wazuh API 请求失败，将在下次轮询重试: %s", exc)
                except Exception as exc:
                    logger.error("HIDS 采集异常: %s", exc, exc_info=True)

                await asyncio.sleep(self.poll_interval)

    async def _ensure_token(self, client: httpx.AsyncClient):
        """获取或刷新 Wazuh JWT Token"""
        if self._token:
            return
        try:
            resp = await client.post(
                f"{self.url}/security/user/authenticate",
                auth=(self.user, self.password),
            )
            resp.raise_for_status()
            self._token = resp.json().get("data", {}).get("token")
            if self._token:
                logger.info("Wazuh 认证成功")
            else:
                logger.warning("Wazuh 认证响应中未找到 token")
        except Exception as exc:
            logger.warning("Wazuh 认证失败: %s", exc)
            self._token = None

    def _auth_headers(self) -> dict:
        """构造带 JWT 的请求头"""
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers
