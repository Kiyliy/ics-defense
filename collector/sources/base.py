"""数据源采集器基类"""
from abc import ABC, abstractmethod
from typing import AsyncIterator
import logging

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """数据源采集器基类"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.source_type: str = "unknown"
        self._running: bool = False

    @abstractmethod
    async def collect(self) -> AsyncIterator[dict]:
        """采集原始日志，yield 每条原始事件 dict"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查数据源连接是否正常"""
        ...

    async def start(self):
        """启动采集器（可选覆盖）"""
        self._running = True
        logger.info("采集器 %s 已启动", self.source_type)

    async def stop(self):
        """停止采集器（可选覆盖）"""
        self._running = False
        logger.info("采集器 %s 已停止", self.source_type)
