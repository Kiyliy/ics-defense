"""PIKACHU 靶场数据源采集器

监控指定目录下新产生的 JSON 日志文件，输出格式与 normalizer.normalize_pikachu() 对齐。
典型字段: vuln_type/vul_type, payload, src_ip/attacker_ip, dst_ip/target_ip
"""

import asyncio
import json
import logging
import os
from typing import AsyncIterator

from .base import BaseCollector

logger = logging.getLogger(__name__)


class PikachuCollector(BaseCollector):
    """PIKACHU 靶场采集器，监控目录下新增 JSON 日志文件"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.source_type = "pikachu"
        self.watch_dir = self.config.get("watch_dir", "/var/log/pikachu/")
        self.poll_interval = self.config.get("poll_interval", 5)
        self._processed_files: set[str] = set()
        self._file_offsets: dict[str, int] = {}

    async def health_check(self) -> bool:
        """检查监控目录是否存在且可读"""
        try:
            return os.path.isdir(self.watch_dir) and os.access(self.watch_dir, os.R_OK)
        except Exception as exc:
            logger.warning("PIKACHU 健康检查失败: %s", exc)
            return False

    async def start(self):
        """启动时记录目录中已有文件，避免重复采集"""
        await super().start()
        try:
            if os.path.isdir(self.watch_dir):
                for name in os.listdir(self.watch_dir):
                    if name.endswith(".json"):
                        full_path = os.path.join(self.watch_dir, name)
                        self._processed_files.add(full_path)
                        self._file_offsets[full_path] = os.path.getsize(full_path)
                logger.info(
                    "PIKACHU 采集器初始化，已有 %d 个 JSON 文件",
                    len(self._processed_files),
                )
        except OSError as exc:
            logger.warning("扫描 PIKACHU 目录失败: %s", exc)

    async def collect(self) -> AsyncIterator[dict]:
        """持续扫描目录，读取新增或追加的 JSON 日志"""
        while self._running:
            try:
                if not os.path.isdir(self.watch_dir):
                    logger.warning("PIKACHU 监控目录不存在: %s", self.watch_dir)
                    await asyncio.sleep(self.poll_interval)
                    continue

                for name in sorted(os.listdir(self.watch_dir)):
                    if not name.endswith(".json"):
                        continue

                    full_path = os.path.join(self.watch_dir, name)
                    if not os.path.isfile(full_path):
                        continue

                    async for event in self._read_file(full_path):
                        yield event

            except Exception as exc:
                logger.error("PIKACHU 采集异常: %s", exc, exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _read_file(self, path: str) -> AsyncIterator[dict]:
        """读取单个 JSON 日志文件的新增内容"""
        try:
            current_size = os.path.getsize(path)
            prev_offset = self._file_offsets.get(path, 0)

            # 文件被截断时重置
            if current_size < prev_offset:
                prev_offset = 0

            if current_size <= prev_offset:
                return

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(prev_offset)
                content = f.read()
                new_offset = f.tell()

            self._file_offsets[path] = new_offset
            self._processed_files.add(path)

            # 尝试按行解析（JSON Lines 格式）
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if isinstance(event, dict):
                        yield event
                    elif isinstance(event, list):
                        for item in event:
                            if isinstance(item, dict):
                                yield item
                except json.JSONDecodeError:
                    pass

            # 如果按行解析没结果，尝试整体解析
            if not content.strip().startswith("{") and not content.strip().startswith("["):
                return
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    yield data
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            yield item
            except json.JSONDecodeError:
                pass

        except OSError as exc:
            logger.warning("读取 PIKACHU 日志文件失败 %s: %s", path, exc)
