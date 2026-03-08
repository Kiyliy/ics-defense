"""SOC 通用 Syslog 数据源采集器

监听 UDP Syslog 端口接收日志，解析后输出格式与 normalizer.normalize_soc() 对齐。
典型字段: title/message, description, severity, src_ip, dst_ip
"""

import asyncio
import json
import logging
import re
from typing import AsyncIterator

from .base import BaseCollector

logger = logging.getLogger(__name__)

# 简易 syslog 消息正则：<priority>timestamp hostname message
_SYSLOG_RE = re.compile(
    r"^<(\d{1,3})>"
    r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})?\s*"
    r"(\S+)?\s+"
    r"(.+)$"
)

# Syslog severity 映射（RFC 5424 severity 0-7）
_SYSLOG_SEVERITY = {
    0: "critical",  # Emergency
    1: "critical",  # Alert
    2: "critical",  # Critical
    3: "high",      # Error
    4: "medium",    # Warning
    5: "medium",    # Notice
    6: "low",       # Informational
    7: "low",       # Debug
}


class _SyslogProtocol(asyncio.DatagramProtocol):
    """UDP Syslog 协议处理器"""

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue

    def datagram_received(self, data: bytes, addr: tuple):
        try:
            message = data.decode("utf-8", errors="replace").strip()
            if message:
                self._queue.put_nowait((message, addr))
        except Exception as exc:
            logger.debug("Syslog 数据包处理失败: %s", exc)

    def error_received(self, exc):
        logger.warning("Syslog UDP 错误: %s", exc)


class SOCCollector(BaseCollector):
    """SOC 通用采集器，通过 UDP Syslog 接收日志"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.source_type = "soc"
        self.host = self.config.get("host", "0.0.0.0")
        self.port = self.config.get("port", 514)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._transport: asyncio.DatagramTransport | None = None

    async def health_check(self) -> bool:
        """检查 Syslog 监听是否正常"""
        return self._transport is not None and not self._transport.is_closing()

    async def start(self):
        """启动 UDP Syslog 监听"""
        await super().start()
        loop = asyncio.get_running_loop()
        try:
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: _SyslogProtocol(self._queue),
                local_addr=(self.host, self.port),
            )
            logger.info("SOC Syslog 监听已启动 %s:%d/udp", self.host, self.port)
        except OSError as exc:
            logger.error("无法绑定 Syslog 端口 %s:%d: %s", self.host, self.port, exc)
            raise

    async def stop(self):
        """关闭 UDP 监听"""
        if self._transport:
            self._transport.close()
            self._transport = None
        await super().stop()

    async def collect(self) -> AsyncIterator[dict]:
        """从队列中消费 Syslog 消息，解析为 dict"""
        while self._running:
            try:
                message, addr = await asyncio.wait_for(
                    self._queue.get(), timeout=2.0
                )
                event = self._parse_syslog(message, addr)
                if event:
                    yield event
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.error("SOC 采集异常: %s", exc, exc_info=True)

    def _parse_syslog(self, message: str, addr: tuple) -> dict | None:
        """解析 syslog 消息为 dict"""
        # 尝试直接 JSON 解析（结构化 syslog）
        try:
            event = json.loads(message)
            if isinstance(event, dict):
                event.setdefault("src_ip", addr[0])
                return event
        except (json.JSONDecodeError, ValueError):
            pass

        # 标准 syslog 格式解析
        match = _SYSLOG_RE.match(message)
        if match:
            priority = int(match.group(1))
            severity_num = priority & 0x07
            return {
                "title": f"Syslog from {match.group(3) or addr[0]}",
                "message": match.group(4),
                "severity": _SYSLOG_SEVERITY.get(severity_num, "low"),
                "src_ip": addr[0],
                "timestamp": match.group(2),
            }

        # 无法解析时作为原始消息返回
        return {
            "title": "Raw Syslog",
            "message": message,
            "severity": "low",
            "src_ip": addr[0],
        }
