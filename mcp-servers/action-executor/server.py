import json
import logging
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="action-executor", instructions="ICS 安全处置执行服务")
logger = logging.getLogger("action-executor")

# 执行记录（内存，生产环境应持久化）
execution_log = []


@mcp.tool()
def block_ip(ip: str, reason: str = "", duration_hours: int = 24) -> str:
    """下发防火墙规则阻断IP

    ⚠️ 高危操作，需要人工审批后才会实际调用此工具。

    Args:
        ip: 要阻断的IP地址
        reason: 阻断原因
        duration_hours: 阻断时长（小时），默认24

    Returns:
        JSON: {"status": "executed", "ip": "...", "action": "block_ip", "duration_hours": 24, "executed_at": "..."}
    """
    record = {
        "action": "block_ip",
        "ip": ip,
        "reason": reason,
        "duration_hours": duration_hours,
        "executed_at": datetime.now().isoformat(),
        "status": "executed",
    }
    execution_log.append(record)
    logger.warning(f"BLOCK IP: {ip} for {duration_hours}h - {reason}")
    return json.dumps(record, ensure_ascii=False)


@mcp.tool()
def isolate_host(ip: str, reason: str = "") -> str:
    """网络隔离主机

    ⚠️ 高危操作，需要人工审批后才会实际调用此工具。

    Args:
        ip: 要隔离的主机IP
        reason: 隔离原因

    Returns:
        JSON: {"status": "executed", "ip": "...", "action": "isolate_host", "executed_at": "..."}
    """
    record = {
        "action": "isolate_host",
        "ip": ip,
        "reason": reason,
        "executed_at": datetime.now().isoformat(),
        "status": "executed",
    }
    execution_log.append(record)
    logger.warning(f"ISOLATE HOST: {ip} - {reason}")
    return json.dumps(record, ensure_ascii=False)


@mcp.tool()
def add_watch(target: str, watch_type: str = "monitor", description: str = "") -> str:
    """添加监控/告警规则

    Args:
        target: 监控目标（IP、主机名、或规则描述）
        watch_type: 监控类型 (monitor/alert/investigate)
        description: 规则描述

    Returns:
        JSON: {"status": "created", "target": "...", "watch_type": "...", "created_at": "..."}
    """
    record = {
        "action": "add_watch",
        "target": target,
        "watch_type": watch_type,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "status": "created",
    }
    execution_log.append(record)
    return json.dumps(record, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
