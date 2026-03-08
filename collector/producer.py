"""
Redis Streams 生产者模块

将聚簇后的告警推送到 Redis Streams 供下游消费。
"""

import json
import redis


class AlertProducer:
    """将聚簇后的告警推送到 Redis Streams"""

    def __init__(self, redis_url: str = "redis://localhost:6379", stream_key: str = "ics:alerts"):
        self.redis_url = redis_url
        self.stream_key = stream_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = redis.from_url(self.redis_url)
        return self._client

    def publish(self, clustered_alert: dict) -> str:
        """发布一条聚簇告警到 Redis Streams
        返回 message_id
        """
        if not isinstance(clustered_alert, dict):
            raise TypeError("clustered_alert must be a dict")
        client = self._get_client()
        return client.xadd(self.stream_key, {"data": json.dumps(clustered_alert, ensure_ascii=False)})

    def publish_batch(self, alerts: list[dict]) -> list[str]:
        """批量发布"""
        return [self.publish(a) for a in alerts]

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
