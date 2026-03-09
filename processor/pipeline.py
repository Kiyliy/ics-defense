"""
事件处理管线 — 将多源原始事件经过 规范化 → 聚簇 → 分级 → 入库/投递 的完整流程。

典型用法::

    pipeline = Pipeline(db_path="data/ics.db", redis_url="redis://localhost:6379")
    await pipeline.process_event("waf", {"rule_name": "SQL注入", "severity": "high", ...})
    result = await pipeline.flush()
    # result => {"analyzed": 1, "stored": 3}
"""

import json
import logging
import time
from typing import Optional

from agent.db import init_db, get_db
from collector.normalizer import normalize, NormalizedAlert
from collector.clusterer import AlertClusterer, ClusteredAlert
from collector.severity_filter import SeverityFilter
from collector.producer import AlertProducer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 数据库 Schema — 使用 agent.db 统一数据层
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------
_DEFAULT_FLUSH_COUNT = 50          # 每积累 N 条事件自动 flush
_DEFAULT_FLUSH_INTERVAL = 60.0     # 距上次 flush 超过 N 秒时自动 flush


class Pipeline:
    """事件处理管线

    Parameters
    ----------
    db_path : str
        SQLite 数据库路径，会自动创建所需表。
    redis_url : str | None
        Redis 连接地址。为 ``None`` 时仅写入 SQLite，不投递到 Redis Streams。
    cluster_window : int
        聚簇时间窗口（秒），默认 300。
    flush_count : int
        每积累多少条事件后自动触发 flush，默认 50。
    flush_interval : float
        距上次 flush 超过多少秒后自动触发 flush，默认 60.0。
    stream_key : str
        Redis Streams 的 key，默认 ``ics:alerts``。
    """

    def __init__(
        self,
        db_path: str,
        redis_url: Optional[str] = "redis://localhost:6379",
        cluster_window: int = 300,
        flush_count: int = _DEFAULT_FLUSH_COUNT,
        flush_interval: float = _DEFAULT_FLUSH_INTERVAL,
        stream_key: str = "ics:alerts",
    ):
        self.db_path = db_path
        self.redis_url = redis_url
        self.stream_key = stream_key

        # 聚簇器
        self._clusterer = AlertClusterer(window_seconds=cluster_window)

        # 自动 flush 阈值
        self._flush_count = flush_count
        self._flush_interval = flush_interval
        self._pending_count = 0
        self._last_flush_time = time.monotonic()

        # 初始化 SQLite (via unified data layer)
        init_db(db_path)
        self._db_ctx = get_db(db_path)
        self._db = self._db_ctx.__enter__()

        # Redis 生产者（可选）
        self._producer: Optional[AlertProducer] = None
        if redis_url:
            try:
                self._producer = AlertProducer(
                    redis_url=redis_url,
                    stream_key=stream_key,
                )
                logger.info("Redis 生产者已初始化: %s / %s", redis_url, stream_key)
            except Exception as exc:
                logger.warning("Redis 生产者初始化失败，将仅写入 SQLite: %s", exc)
                self._producer = None

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _store_raw_event(self, source: str, raw: dict) -> int:
        """将原始事件写入 raw_events 表，返回自增 ID。"""
        raw_json = json.dumps(raw, ensure_ascii=False, default=str)
        cur = self._db.execute(
            "INSERT INTO raw_events (source, raw_json) VALUES (?, ?)",
            (source, raw_json),
        )
        self._db.commit()
        return cur.lastrowid

    def _store_alert(
        self,
        cluster: ClusteredAlert,
        raw_event_id: Optional[int] = None,
        status: str = "open",
    ) -> int:
        """将聚簇告警写入 alerts 表，返回告警 ID。"""
        sample = cluster.sample
        cur = self._db.execute(
            """INSERT INTO alerts
               (source, severity, title, description, src_ip, dst_ip,
                mitre_tactic, mitre_technique, status, raw_event_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sample.get("source", "unknown"),
                cluster.severity,
                sample.get("title", "Unknown"),
                sample.get("description", ""),
                sample.get("src_ip"),
                sample.get("dst_ip"),
                sample.get("mitre_tactic"),
                sample.get("mitre_technique"),
                status,
                raw_event_id,
            ),
        )
        self._db.commit()
        return cur.lastrowid

    def _publish_to_redis(self, cluster: ClusteredAlert, alert_id: int) -> bool:
        """尝试将告警发布到 Redis Streams。失败时仅记录警告。"""
        if self._producer is None:
            return False
        try:
            payload = cluster.to_dict()
            payload["alert_id"] = alert_id
            self._producer.publish(payload)
            return True
        except Exception as exc:
            logger.warning("Redis 投递失败（告警 ID=%s）: %s", alert_id, exc)
            return False

    def _should_auto_flush(self) -> bool:
        """判断是否应触发自动 flush。"""
        if self._pending_count >= self._flush_count:
            return True
        if (time.monotonic() - self._last_flush_time) >= self._flush_interval:
            return True
        return False

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------
    async def process_event(self, source: str, raw: dict) -> NormalizedAlert:
        """处理单条原始事件。

        流程:
        1. 调用 ``normalizer.normalize()`` 得到 NormalizedAlert
        2. 将原始事件写入 ``raw_events`` 表
        3. 加入聚簇器
        4. 若达到自动 flush 条件，触发 flush

        Parameters
        ----------
        source : str
            数据源标识（waf / nids / hids / pikachu / soc）。
        raw : dict
            原始事件字典。

        Returns
        -------
        NormalizedAlert
            规范化后的告警对象。
        """
        # 1. 规范化
        alert = normalize(source, raw)

        # 2. 存储原始事件
        self._store_raw_event(source, raw)

        # 3. 加入聚簇器
        self._clusterer.add(alert.to_dict())
        self._pending_count += 1

        # 4. 条件自动 flush
        if self._should_auto_flush():
            await self.flush()

        return alert

    async def flush(self) -> dict:
        """冲刷聚簇器，对每个聚簇执行分级 + 入库 + 投递。

        Returns
        -------
        dict
            ``{"analyzed": N, "stored": M}``
            - analyzed: 需要 Agent 分析（critical/high），已写入 DB 并投递到 Redis。
            - stored: 仅存储（medium/low），已写入 DB 但不投递。
        """
        clusters = self._clusterer.flush()
        analyzed = 0
        stored = 0

        for cluster in clusters:
            if SeverityFilter.should_analyze(cluster.severity):
                # 需要 Agent 分析 —— 写入 DB + 投递 Redis
                alert_id = self._store_alert(cluster, status="analyzing")
                self._publish_to_redis(cluster, alert_id)
                analyzed += 1
            else:
                # 仅存储
                self._store_alert(cluster, status="open")
                stored += 1

        self._pending_count = 0
        self._last_flush_time = time.monotonic()

        logger.info(
            "flush 完成: %d 个聚簇（analyzed=%d, stored=%d）",
            len(clusters), analyzed, stored,
        )
        return {"analyzed": analyzed, "stored": stored}

    async def process_batch(self, events: list[tuple[str, dict]]) -> dict:
        """批量处理多条原始事件。

        Parameters
        ----------
        events : list[tuple[str, dict]]
            每个元素为 ``(source, raw_dict)``。

        Returns
        -------
        dict
            与 :meth:`flush` 返回格式相同。
        """
        for source, raw in events:
            alert = normalize(source, raw)
            self._store_raw_event(source, raw)
            self._clusterer.add(alert.to_dict())
            self._pending_count += 1

        return await self.flush()

    def close(self):
        """释放资源：关闭 Redis 连接和 SQLite 连接。"""
        if self._producer:
            try:
                self._producer.close()
            except Exception as exc:
                logger.warning("关闭 Redis 生产者时出错: %s", exc)
            self._producer = None
        if self._db:
            try:
                self._db.close()
            except Exception as exc:
                logger.warning("关闭 SQLite 连接时出错: %s", exc)
            self._db = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
