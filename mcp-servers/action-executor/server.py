import json
import logging
import re
import uuid
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("action-executor")

mcp = FastMCP(name="action-executor", instructions="ICS 安全处置执行服务")

# 执行记录（内存，生产环境应持久化）
execution_log = []

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
_IP_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)
_HOSTNAME_PATTERN = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$"
)


def _validate_ip(ip: str, field_name: str = "ip") -> str:
    """Validate an IPv4 address string."""
    if not ip or not ip.strip():
        raise ValueError(f"{field_name} 不能为空")
    ip = ip.strip()
    if not _IP_PATTERN.match(ip):
        raise ValueError(f"{field_name} 格式无效: '{ip}'，需要有效的IPv4地址")
    return ip


def _validate_ip_or_hostname(value: str, field_name: str = "target") -> str:
    """Validate an IPv4 address or hostname string."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    value = value.strip()
    if not _IP_PATTERN.match(value) and not _HOSTNAME_PATTERN.match(value):
        raise ValueError(f"{field_name} 格式无效: '{value}'，需要有效的IP地址或主机名")
    return value


def _make_action_id() -> str:
    """Generate a unique action ID."""
    return f"act-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def block_ip(ip: str, reason: str = "", duration_hours: int = 24) -> str:
    """下发防火墙规则阻断IP

    ⚠️ 高危操作，需要人工审批后才会实际调用此工具。

    Args:
        ip: 要阻断的IP地址
        reason: 阻断原因
        duration_hours: 阻断时长（小时），默认24

    Returns:
        JSON: {"status": "executed", "action_id": "...", "ip": "...", "action": "block_ip", "duration_hours": 24, "executed_at": "..."}
    """
    try:
        ip = _validate_ip(ip, "ip")
    except ValueError as exc:
        logger.warning("block_ip 参数校验失败: %s", exc)
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)

    if not isinstance(duration_hours, int) or duration_hours < 1:
        logger.warning("block_ip: duration_hours 无效: %s", duration_hours)
        return json.dumps({"status": "error", "error": "duration_hours 必须为正整数"}, ensure_ascii=False)

    action_id = _make_action_id()
    now = datetime.now().isoformat()

    record = {
        "action_id": action_id,
        "action": "block_ip",
        "ip": ip,
        "reason": reason,
        "duration_hours": duration_hours,
        "executed_at": now,
        "status": "executed",
        "detail": f"[DEMO] 防火墙规则已下发: iptables -A INPUT -s {ip} -j DROP (有效期 {duration_hours}h)",
    }
    execution_log.append(record)
    logger.warning("BLOCK IP: action_id=%s ip=%s duration=%dh reason=%s", action_id, ip, duration_hours, reason)
    return json.dumps(record, ensure_ascii=False)


@mcp.tool()
def isolate_host(ip: str, reason: str = "") -> str:
    """网络隔离主机

    ⚠️ 高危操作，需要人工审批后才会实际调用此工具。

    Args:
        ip: 要隔离的主机IP
        reason: 隔离原因

    Returns:
        JSON: {"status": "executed", "action_id": "...", "ip": "...", "action": "isolate_host", "executed_at": "..."}
    """
    try:
        ip = _validate_ip(ip, "ip")
    except ValueError as exc:
        logger.warning("isolate_host 参数校验失败: %s", exc)
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)

    action_id = _make_action_id()
    now = datetime.now().isoformat()

    record = {
        "action_id": action_id,
        "action": "isolate_host",
        "ip": ip,
        "reason": reason,
        "executed_at": now,
        "status": "executed",
        "detail": f"[DEMO] 主机隔离指令已下发: 交换机 ACL 隔离 {ip}，仅保留管理通道",
    }
    execution_log.append(record)
    logger.warning("ISOLATE HOST: action_id=%s ip=%s reason=%s", action_id, ip, reason)
    return json.dumps(record, ensure_ascii=False)


@mcp.tool()
def add_watch(target: str, watch_type: str = "monitor", description: str = "") -> str:
    """添加监控/告警规则

    Args:
        target: 监控目标（IP、主机名、或规则描述）
        watch_type: 监控类型 (monitor/alert/investigate)
        description: 规则描述

    Returns:
        JSON: {"status": "created", "action_id": "...", "target": "...", "watch_type": "...", "created_at": "..."}
    """
    if not target or not target.strip():
        logger.warning("add_watch: target 为空")
        return json.dumps({"status": "error", "error": "target 不能为空"}, ensure_ascii=False)
    target = target.strip()

    valid_watch_types = {"monitor", "alert", "investigate"}
    if watch_type not in valid_watch_types:
        logger.warning("add_watch: 无效的 watch_type: %s", watch_type)
        return json.dumps(
            {"status": "error", "error": f"watch_type 无效，可选: {', '.join(sorted(valid_watch_types))}"},
            ensure_ascii=False,
        )

    action_id = _make_action_id()
    now = datetime.now().isoformat()

    record = {
        "action_id": action_id,
        "action": "add_watch",
        "target": target,
        "watch_type": watch_type,
        "description": description,
        "created_at": now,
        "status": "created",
        "detail": f"[DEMO] 监控规则已创建: 类型={watch_type} 目标={target}",
    }
    execution_log.append(record)
    logger.info("ADD WATCH: action_id=%s target=%s type=%s", action_id, target, watch_type)
    return json.dumps(record, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
