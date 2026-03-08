"""雷池 WAF 数据源采集器

通过轮询雷池 WAF API 获取最新安全事件，输出格式与 normalizer.normalize_waf() 对齐。
典型字段: rule_name, severity, src_ip, dst_ip, url, payload
"""

import asyncio
import logging
from typing import AsyncIterator

import httpx

from .base import BaseCollector

logger = logging.getLogger(__name__)


class WAFCollector(BaseCollector):
    """雷池 WAF 采集器，通过 REST API 轮询安全事件"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.source_type = "waf"
        self.url = self.config.get("url", "http://localhost:9443/api/events")
        self.api_key = self.config.get("api_key", "")
        self.poll_interval = self.config.get("poll_interval", 10)
        self._last_event_id: str | None = None

    async def health_check(self) -> bool:
        """检查 WAF API 是否可达"""
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.get(
                    self.url,
                    headers=self._headers(),
                    params={"limit": 1},
                )
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("WAF 健康检查失败: %s", exc)
            return False

    async def collect(self) -> AsyncIterator[dict]:
        """持续轮询 WAF API，yield 每条原始事件"""
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            while self._running:
                try:
                    params: dict = {"limit": 100}
                    if self._last_event_id:
                        params["after"] = self._last_event_id

                    resp = await client.get(
                        self.url,
                        headers=self._headers(),
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    # 雷池 API 返回格式可能为 {"data": [...]} 或直接列表
                    events = data if isinstance(data, list) else data.get("data", [])

                    for event in events:
                        event_id = event.get("id") or event.get("event_id")
                        if event_id:
                            self._last_event_id = str(event_id)
                        yield event

                except httpx.HTTPStatusError as exc:
                    logger.warning("WAF API 返回错误状态码 %s: %s", exc.response.status_code, exc)
                except httpx.RequestError as exc:
                    logger.warning("WAF API 请求失败，将在下次轮询重试: %s", exc)
                except Exception as exc:
                    logger.error("WAF 采集异常: %s", exc, exc_info=True)

                await asyncio.sleep(self.poll_interval)

    def _headers(self) -> dict:
        """构造请求头"""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
