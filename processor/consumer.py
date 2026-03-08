"""
Redis Streams 消费者 — 从队列中拉取聚簇告警并触发 Agent 分析。

典型用法::

    consumer = AlertConsumer(config={
        "redis_url": "redis://localhost:6379",
        "stream_key": "ics:alerts",
        "group": "agent-consumers",
        "consumer_name": "consumer-1",
        "agent_url": "http://localhost:8000",
    })
    await consumer.run()          # 阻塞运行，直到 shutdown
    await consumer.shutdown()     # 优雅停机
"""

import asyncio
import json
import logging
from typing import Optional

import redis
import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG = {
    "redis_url": "redis://localhost:6379",
    "stream_key": "ics:alerts",
    "group": "agent-consumers",
    "consumer_name": "consumer-1",
    "agent_url": "http://localhost:8000",
}

# 读取阻塞超时（毫秒），用于 XREADGROUP BLOCK
_BLOCK_MS = 5000
# Agent 分析接口请求超时（秒）
_AGENT_TIMEOUT = 120.0


class AlertConsumer:
    """Redis Streams 消费者

    从 ``ics:alerts`` 流中拉取聚簇告警消息，调用 Agent 服务 HTTP 接口
    触发分析，并在成功后 ACK 消息。

    Parameters
    ----------
    config : dict | None
        配置字典，可包含以下键：

        - ``redis_url``     — Redis 连接地址
        - ``stream_key``    — Stream 名称
        - ``group``         — 消费者组名
        - ``consumer_name`` — 消费者实例名
        - ``agent_url``     — Agent 服务根 URL
    """

    def __init__(self, config: Optional[dict] = None):
        cfg = {**_DEFAULT_CONFIG, **(config or {})}
        self.redis_url: str = cfg["redis_url"]
        self.stream_key: str = cfg["stream_key"]
        self.group: str = cfg["group"]
        self.consumer_name: str = cfg["consumer_name"]
        self.agent_url: str = cfg["agent_url"].rstrip("/")

        self._client: Optional[redis.Redis] = None
        self._http: Optional[httpx.AsyncClient] = None
        self._running: bool = False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _get_redis(self) -> redis.Redis:
        """懒初始化 Redis 客户端。"""
        if self._client is None:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def _ensure_group(self):
        """确保消费者组存在（若不存在则创建）。"""
        client = self._get_redis()
        try:
            client.xgroup_create(
                name=self.stream_key,
                groupname=self.group,
                id="0",
                mkstream=True,
            )
            logger.info(
                "消费者组已创建: stream=%s group=%s",
                self.stream_key, self.group,
            )
        except redis.ResponseError as exc:
            # BUSYGROUP 表示组已存在，忽略
            if "BUSYGROUP" in str(exc):
                logger.debug("消费者组已存在: %s", self.group)
            else:
                raise

    async def _get_http(self) -> httpx.AsyncClient:
        """懒初始化异步 HTTP 客户端。"""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=_AGENT_TIMEOUT)
        return self._http

    async def _trigger_agent(self, alert_data: dict) -> bool:
        """调用 Agent 服务的分析接口。

        Parameters
        ----------
        alert_data : dict
            聚簇告警数据。

        Returns
        -------
        bool
            调用是否成功（HTTP 2xx）。
        """
        url = f"{self.agent_url}/api/analyze"
        try:
            http = await self._get_http()
            resp = await http.post(url, json=alert_data)
            if resp.is_success:
                logger.info(
                    "Agent 分析已触发: alert_id=%s status=%s",
                    alert_data.get("alert_id", "N/A"), resp.status_code,
                )
                return True
            else:
                logger.warning(
                    "Agent 返回非成功状态: %s %s", resp.status_code, resp.text[:200],
                )
                return False
        except httpx.TimeoutException:
            logger.error("Agent 分析请求超时: %s", url)
            return False
        except Exception as exc:
            logger.error("Agent 分析请求异常: %s", exc)
            return False

    def _ack(self, message_id: str):
        """ACK 一条已处理的消息。"""
        client = self._get_redis()
        client.xack(self.stream_key, self.group, message_id)

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------
    async def run(self):
        """启动消费循环，阻塞直到 :meth:`shutdown` 被调用。

        流程:
        1. 确保消费者组存在
        2. 循环调用 ``XREADGROUP`` 拉取新消息
        3. 对每条消息解析 JSON 并调用 Agent 分析
        4. 分析成功后 ACK 消息
        """
        self._running = True
        self._ensure_group()
        client = self._get_redis()
        logger.info(
            "消费者启动: stream=%s group=%s consumer=%s",
            self.stream_key, self.group, self.consumer_name,
        )

        while self._running:
            try:
                # XREADGROUP 阻塞读取
                # redis-py 的 xreadgroup 是同步的，放到线程池执行以免阻塞事件循环
                messages = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.xreadgroup(
                        groupname=self.group,
                        consumername=self.consumer_name,
                        streams={self.stream_key: ">"},
                        count=10,
                        block=_BLOCK_MS,
                    ),
                )

                if not messages:
                    continue

                for _stream, entries in messages:
                    for message_id, fields in entries:
                        await self._handle_message(message_id, fields)

            except asyncio.CancelledError:
                logger.info("消费者收到取消信号，退出循环")
                break
            except redis.ConnectionError as exc:
                logger.error("Redis 连接丢失，5 秒后重试: %s", exc)
                await asyncio.sleep(5)
            except Exception as exc:
                logger.error("消费循环异常: %s", exc, exc_info=True)
                await asyncio.sleep(1)

        logger.info("消费者已停止")

    async def _handle_message(self, message_id: str, fields: dict):
        """处理单条 Stream 消息。"""
        raw_data = fields.get("data")
        if not raw_data:
            logger.warning("收到空消息: %s", message_id)
            self._ack(message_id)
            return

        try:
            alert_data = json.loads(raw_data)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("消息 JSON 解析失败: %s — %s", message_id, exc)
            self._ack(message_id)
            return

        success = await self._trigger_agent(alert_data)
        if success:
            self._ack(message_id)
            logger.debug("消息已 ACK: %s", message_id)
        else:
            # 不 ACK，下次 pending 列表会重新投递
            logger.warning("消息未 ACK（将重试）: %s", message_id)

    async def shutdown(self):
        """优雅停机：停止消费循环并释放资源。"""
        logger.info("正在停止消费者...")
        self._running = False

        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

        if self._client:
            try:
                self._client.close()
            except Exception as exc:
                logger.warning("关闭 Redis 客户端时出错: %s", exc)
            self._client = None

        logger.info("消费者资源已释放")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()
        return False
