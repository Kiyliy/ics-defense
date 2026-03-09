"""
Collector 主入口

将多源安全数据采集 -> 规范化 -> 聚簇 -> 分级过滤 -> 写入 SQLite（或推送 Redis）。

用法:
    # 作为独立服务运行（使用 demo 数据生成器）
    python -m collector.main --demo

    # 作为独立服务运行（从真实数据源采集）
    python -m collector.main --sources waf,nids

    # 被其他模块导入
    from collector.main import CollectorPipeline
"""

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Optional

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agent.db import init_db, get_db as _get_db_ctx
from collector.normalizer import normalize, NormalizedAlert
from collector.clusterer import AlertClusterer
from collector.severity_filter import SeverityFilter

logger = logging.getLogger("collector")

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------
DB_PATH = (
    os.environ.get("ICS_DB_PATH")
    or os.environ.get("DB_PATH")
    or os.path.join(_PROJECT_ROOT, "backend", "data", "ics_defense.db")
)


class CollectorPipeline:
    """Collector pipeline: normalize -> cluster -> severity_filter -> store.

    Supports two output modes:
    - SQLite direct insert (default, no Redis needed)
    - Redis Streams (when redis_url is provided)
    """

    def __init__(
        self,
        db_path: str = DB_PATH,
        redis_url: Optional[str] = None,
        cluster_window: int = 300,
    ):
        self.db_path = db_path
        self.redis_url = redis_url
        self.clusterer = AlertClusterer(window_seconds=cluster_window)
        self._producer = None
        self._running = False
        self._db_initialized = False
        self._stats = {
            "total_received": 0,
            "total_normalized": 0,
            "total_stored": 0,
            "total_for_agent": 0,
            "total_store_only": 0,
            "errors": 0,
        }

    def _ensure_db(self):
        """Initialize the database using the unified schema (once)."""
        if not self._db_initialized:
            init_db(self.db_path)
            self._db_initialized = True

    def _get_producer(self):
        """Get Redis producer (lazy init)."""
        if self._producer is None and self.redis_url:
            try:
                from collector.producer import AlertProducer
                self._producer = AlertProducer(redis_url=self.redis_url)
                logger.info("Redis producer 已连接: %s", self.redis_url)
            except Exception as exc:
                logger.warning("Redis 连接失败，回退到 SQLite 直插模式: %s", exc)
                self.redis_url = None
        return self._producer

    def process_event(self, source: str, raw_event: dict) -> Optional[dict]:
        """Process a single raw event through the pipeline.

        Returns the normalized alert dict if stored, None if an error occurred.
        """
        self._stats["total_received"] += 1

        try:
            # 1. Store raw event
            self._store_raw_event(source, raw_event)

            # 2. Normalize
            alert = normalize(source, raw_event)
            self._stats["total_normalized"] += 1

            alert_dict = alert.to_dict()

            # 3. Cluster
            sig = self.clusterer.add(alert_dict)
            alert_dict["cluster_signature"] = sig

            # 4. Severity filter
            should_analyze = SeverityFilter.should_analyze(alert_dict.get("severity", "low"))
            if should_analyze:
                self._stats["total_for_agent"] += 1
            else:
                self._stats["total_store_only"] += 1

            # 5. Store / publish
            if self.redis_url and self._get_producer():
                try:
                    self._producer.publish(alert_dict)
                except Exception as exc:
                    logger.warning("Redis 发布失败，回退到 SQLite: %s", exc)
                    self._store_alert(alert_dict)
            else:
                self._store_alert(alert_dict)

            self._stats["total_stored"] += 1
            return alert_dict

        except Exception as exc:
            self._stats["errors"] += 1
            logger.error("处理事件失败: %s", exc, exc_info=True)
            return None

    def process_batch(self, source: str, events: list[dict]) -> list[dict]:
        """Process a batch of raw events. Returns list of stored alert dicts."""
        results = []
        for event in events:
            result = self.process_event(source, event)
            if result:
                results.append(result)
        return results

    def flush_clusters(self) -> list[dict]:
        """Flush expired clusters and return them."""
        expired = self.clusterer.flush_expired()
        return [c.to_dict() for c in expired]

    def get_stats(self) -> dict:
        """Return pipeline statistics."""
        return {**self._stats, "active_clusters": len(self.clusterer.get_clusters())}

    def _store_raw_event(self, source: str, raw_event: dict):
        """Store raw event to SQLite via the unified db layer."""
        self._ensure_db()
        try:
            with _get_db_ctx(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO raw_events (source, raw_json, received_at) VALUES (?, ?, ?)",
                    [
                        source,
                        json.dumps(raw_event, ensure_ascii=False, default=str),
                        datetime.now(timezone.utc).isoformat(),
                    ],
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("存储原始事件失败: %s", exc)

    def _store_alert(self, alert_dict: dict):
        """Store normalized alert to SQLite via the unified db layer."""
        self._ensure_db()
        try:
            now = datetime.now(timezone.utc).isoformat()
            with _get_db_ctx(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO alerts
                       (source, title, description, severity, src_ip, dst_ip,
                        src_port, dst_port, protocol, raw_json,
                        mitre_tactic, mitre_technique, status,
                        cluster_signature, cluster_count, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        alert_dict.get("source"),
                        alert_dict.get("title"),
                        alert_dict.get("description"),
                        alert_dict.get("severity", "low"),
                        alert_dict.get("src_ip"),
                        alert_dict.get("dst_ip"),
                        alert_dict.get("src_port"),
                        alert_dict.get("dst_port"),
                        alert_dict.get("protocol"),
                        alert_dict.get("raw_json"),
                        alert_dict.get("mitre_tactic"),
                        alert_dict.get("mitre_technique"),
                        "open",
                        alert_dict.get("cluster_signature"),
                        1,
                        alert_dict.get("timestamp") or now,
                        now,
                    ],
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error("存储告警失败: %s", exc)

    async def run_with_sources(self, source_configs: dict):
        """Run the collector pipeline with real data sources.

        Args:
            source_configs: dict mapping source names to config dicts, e.g.
                {"waf": {"url": "..."}, "nids": {"log_path": "..."}}
        """
        from collector.sources import (
            WAFCollector, NIDSCollector, HIDSCollector,
            SOCCollector, PikachuCollector,
        )

        source_classes = {
            "waf": WAFCollector,
            "nids": NIDSCollector,
            "hids": HIDSCollector,
            "soc": SOCCollector,
            "pikachu": PikachuCollector,
        }

        collectors = []
        for name, config in source_configs.items():
            cls = source_classes.get(name)
            if cls:
                collector = cls(config)
                collectors.append((name, collector))
                logger.info("初始化数据源: %s", name)
            else:
                logger.warning("未知数据源: %s", name)

        if not collectors:
            logger.error("没有可用的数据源")
            return

        self._running = True

        # Start all collectors
        for name, collector in collectors:
            await collector.start()

        # Collect from all sources concurrently
        async def _collect_from(name: str, collector):
            try:
                async for event in collector.collect():
                    if not self._running:
                        break
                    self.process_event(name, event)
            except Exception as exc:
                logger.error("数据源 %s 采集异常: %s", name, exc, exc_info=True)

        tasks = [asyncio.create_task(_collect_from(n, c)) for n, c in collectors]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Collector pipeline 已停止")
        finally:
            for name, collector in collectors:
                await collector.stop()
            self._running = False

    async def run_demo(self, count: int = 50, interval: float = 1.0):
        """Run with demo data generator.

        Args:
            count: Number of demo events to generate (0 = infinite)
            interval: Seconds between events
        """
        from collector.demo_generator import DemoGenerator

        generator = DemoGenerator()
        self._running = True
        generated = 0

        logger.info("启动 Demo 数据生成器: count=%d interval=%.1fs", count, interval)

        try:
            while self._running:
                event = generator.generate_one()
                source = event.pop("_source", "soc")
                self.process_event(source, event)
                generated += 1

                if generated % 10 == 0:
                    stats = self.get_stats()
                    logger.info(
                        "Demo 进度: generated=%d stored=%d for_agent=%d errors=%d",
                        generated, stats["total_stored"],
                        stats["total_for_agent"], stats["errors"],
                    )

                if count > 0 and generated >= count:
                    logger.info("Demo 数据生成完毕: %d 条", generated)
                    break

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

        stats = self.get_stats()
        logger.info("Collector pipeline 统计: %s", json.dumps(stats))
        return stats

    def stop(self):
        """Stop the pipeline."""
        self._running = False
        if self._producer:
            try:
                self._producer.close()
            except Exception:
                pass
        logger.info("Collector pipeline 已停止")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="ICS Defense Collector Pipeline")
    parser.add_argument("--demo", action="store_true", help="使用 demo 数据生成器")
    parser.add_argument("--demo-count", type=int, default=50, help="Demo 数据条数 (0=无限)")
    parser.add_argument("--demo-interval", type=float, default=0.5, help="Demo 数据生成间隔(秒)")
    parser.add_argument("--sources", type=str, default="", help="数据源列表，逗号分隔 (waf,nids,hids,soc,pikachu)")
    parser.add_argument("--redis-url", type=str, default="", help="Redis URL (留空则使用 SQLite 直插)")
    parser.add_argument("--db-path", type=str, default="", help="SQLite 数据库路径")
    parser.add_argument("--cluster-window", type=int, default=300, help="聚簇时间窗口(秒)")

    args = parser.parse_args()

    db_path = args.db_path or DB_PATH
    redis_url = args.redis_url or None

    pipeline = CollectorPipeline(
        db_path=db_path,
        redis_url=redis_url,
        cluster_window=args.cluster_window,
    )

    if args.demo:
        asyncio.run(pipeline.run_demo(count=args.demo_count, interval=args.demo_interval))
    elif args.sources:
        source_names = [s.strip() for s in args.sources.split(",") if s.strip()]
        source_configs = {name: {} for name in source_names}
        asyncio.run(pipeline.run_with_sources(source_configs))
    else:
        parser.print_help()
        print("\n请指定 --demo 或 --sources 参数")
        sys.exit(1)


if __name__ == "__main__":
    main()
