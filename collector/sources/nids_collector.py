"""Suricata NIDS 数据源采集器

以 tail -f 方式持续读取 Suricata EVE JSON 日志文件，输出格式与
normalizer.normalize_nids() 对齐。
典型字段: alert.signature, alert.severity, alert.signature_id, src_ip, dest_ip, proto
"""

import asyncio
import json
import logging
import os
from typing import AsyncIterator

from .base import BaseCollector

logger = logging.getLogger(__name__)


class NIDSCollector(BaseCollector):
    """Suricata NIDS 采集器，持续读取 EVE JSON 日志"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.source_type = "nids"
        self.log_path = self.config.get("log_path", "/var/log/suricata/eve.json")
        self.poll_interval = self.config.get("poll_interval", 2)
        self._offset: int = 0

    async def health_check(self) -> bool:
        """检查日志文件是否存在且可读"""
        try:
            return os.path.isfile(self.log_path) and os.access(self.log_path, os.R_OK)
        except Exception as exc:
            logger.warning("NIDS 健康检查失败: %s", exc)
            return False

    async def start(self):
        """启动时跳到文件末尾，只采集新产生的日志"""
        await super().start()
        try:
            if os.path.isfile(self.log_path):
                self._offset = os.path.getsize(self.log_path)
                logger.info("NIDS 采集器从文件偏移 %d 开始", self._offset)
        except OSError as exc:
            logger.warning("获取文件大小失败，将从头读取: %s", exc)
            self._offset = 0

    async def collect(self) -> AsyncIterator[dict]:
        """持续读取 EVE JSON 日志新增行"""
        while self._running:
            try:
                if not os.path.isfile(self.log_path):
                    logger.warning("NIDS 日志文件不存在: %s", self.log_path)
                    await asyncio.sleep(self.poll_interval)
                    continue

                current_size = os.path.getsize(self.log_path)

                # 文件被截断/轮转时重置偏移
                if current_size < self._offset:
                    logger.info("NIDS 日志文件被轮转，重置偏移")
                    self._offset = 0

                if current_size > self._offset:
                    async for event in self._read_new_lines():
                        yield event

            except Exception as exc:
                logger.error("NIDS 采集异常: %s", exc, exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _read_new_lines(self) -> AsyncIterator[dict]:
        """读取文件中从 _offset 开始的新行"""
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        # 只采集告警类型的事件
                        if event.get("event_type") == "alert":
                            yield event
                    except json.JSONDecodeError:
                        logger.debug("NIDS 日志行 JSON 解析失败，跳过: %s", line[:200])
                self._offset = f.tell()
        except OSError as exc:
            logger.warning("读取 NIDS 日志文件失败: %s", exc)
