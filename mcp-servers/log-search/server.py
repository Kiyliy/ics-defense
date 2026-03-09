import json
import logging
import os
import sqlite3
import sys
from mcp.server.fastmcp import FastMCP

# Ensure the project root is on sys.path so ``agent.db`` is importable when
# this MCP server is launched as a subprocess.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agent.db import get_db as _get_db_ctx  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("log-search")

mcp = FastMCP(name="log-search", instructions="ICS 安全告警和日志查询服务")

# 数据库路径通过环境变量配置
DB_PATH = os.environ.get("ICS_DB_PATH") or os.environ.get("DB_PATH") or "backend/data/ics_defense.db"

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_VALID_STATUSES = {"open", "analyzing", "resolved"}
_VALID_SOURCES = {"waf", "nids", "hids", "pikachu", "soc"}


def _validate_severity(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v not in _VALID_SEVERITIES:
        raise ValueError(f"无效的严重级别 '{value}'，可选: {', '.join(sorted(_VALID_SEVERITIES))}")
    return v


def _validate_status(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v not in _VALID_STATUSES:
        raise ValueError(f"无效的状态 '{value}'，可选: {', '.join(sorted(_VALID_STATUSES))}")
    return v


def _validate_source(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v not in _VALID_SOURCES:
        raise ValueError(f"无效的数据源 '{value}'，可选: {', '.join(sorted(_VALID_SOURCES))}")
    return v


def _validate_positive_int(value: int, name: str, max_val: int = 10000) -> int:
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} 必须为正整数，收到: {value}")
    if value > max_val:
        raise ValueError(f"{name} 不能超过 {max_val}，收到: {value}")
    return value


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------
def get_db():
    """Return a context-managed DB connection from the unified data layer.

    For backward compatibility this returns an object that works both as a
    context manager **and** as a plain connection (the tools below call
    ``db = get_db(); db.execute(...)``).  We therefore return the underlying
    connection directly and keep ``sqlite3`` as a fallback import for
    exception types used in except clauses.
    """
    if not os.path.exists(DB_PATH):
        logger.warning("数据库文件不存在: %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def search_alerts(
    severity: str = None,
    src_ip: str = None,
    dst_ip: str = None,
    source: str = None,
    status: str = None,
    hours: int = 24,
    limit: int = 50,
) -> str:
    """按条件查询历史告警

    Args:
        severity: 告警级别过滤 (critical/high/medium/low)
        src_ip: 源IP过滤
        dst_ip: 目标IP过滤
        source: 数据源过滤 (waf/nids/hids/pikachu/soc)
        status: 状态过滤 (open/analyzing/resolved)
        hours: 查询最近N小时的告警，默认24
        limit: 返回条数限制，默认50

    Returns:
        JSON 格式的告警列表
    """
    try:
        severity = _validate_severity(severity)
        status = _validate_status(status)
        source = _validate_source(source)
        hours = _validate_positive_int(hours, "hours", max_val=8760)
        limit = _validate_positive_int(limit, "limit", max_val=1000)
    except ValueError as exc:
        logger.warning("search_alerts 参数校验失败: %s", exc)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    logger.info(
        "search_alerts: severity=%s src_ip=%s dst_ip=%s source=%s status=%s hours=%d limit=%d",
        severity, src_ip, dst_ip, source, status, hours, limit,
    )

    try:
        db = get_db()
    except sqlite3.Error as exc:
        logger.error("数据库连接失败: %s", exc)
        return json.dumps({"error": f"数据库连接失败: {exc}"}, ensure_ascii=False)

    try:
        query = "SELECT * FROM alerts WHERE created_at >= datetime('now', ?)"
        params: list = [f"-{hours} hours"]

        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if src_ip:
            query += " AND src_ip = ?"
            params.append(src_ip)
        if dst_ip:
            query += " AND dst_ip = ?"
            params.append(dst_ip)
        if source:
            query += " AND source = ?"
            params.append(source)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = db.execute(query, params).fetchall()
        results = [dict(r) for r in rows]
        logger.info("search_alerts 返回 %d 条告警", len(results))
        return json.dumps(results, ensure_ascii=False, default=str)
    except sqlite3.Error as exc:
        logger.error("查询告警失败: %s", exc)
        return json.dumps({"error": f"查询失败: {exc}"}, ensure_ascii=False)
    finally:
        db.close()


@mcp.tool()
def search_raw_events(
    source: str = None,
    hours: int = 24,
    limit: int = 50,
) -> str:
    """查询原始事件日志

    Args:
        source: 数据源过滤
        hours: 查询最近N小时
        limit: 返回条数限制

    Returns:
        JSON 格式的原始事件列表
    """
    try:
        source = _validate_source(source)
        hours = _validate_positive_int(hours, "hours", max_val=8760)
        limit = _validate_positive_int(limit, "limit", max_val=1000)
    except ValueError as exc:
        logger.warning("search_raw_events 参数校验失败: %s", exc)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    logger.info("search_raw_events: source=%s hours=%d limit=%d", source, hours, limit)

    try:
        db = get_db()
    except sqlite3.Error as exc:
        logger.error("数据库连接失败: %s", exc)
        return json.dumps({"error": f"数据库连接失败: {exc}"}, ensure_ascii=False)

    try:
        query = "SELECT * FROM raw_events WHERE received_at >= datetime('now', ?)"
        params: list = [f"-{hours} hours"]

        if source:
            query += " AND source = ?"
            params.append(source)

        query += " ORDER BY received_at DESC LIMIT ?"
        params.append(limit)

        rows = db.execute(query, params).fetchall()
        results = [dict(r) for r in rows]
        logger.info("search_raw_events 返回 %d 条事件", len(results))
        return json.dumps(results, ensure_ascii=False, default=str)
    except sqlite3.Error as exc:
        logger.error("查询原始事件失败: %s", exc)
        return json.dumps({"error": f"查询失败: {exc}"}, ensure_ascii=False)
    finally:
        db.close()


@mcp.tool()
def get_alert_context(
    alert_id: int,
    window_minutes: int = 30,
) -> str:
    """获取某告警的上下文（前后时间窗口内的相关事件）

    Args:
        alert_id: 告警ID
        window_minutes: 时间窗口（分钟），默认前后30分钟

    Returns:
        JSON: {"target_alert": {...}, "context_alerts": [...], "raw_events": [...]}
    """
    try:
        if not isinstance(alert_id, int) or alert_id < 1:
            raise ValueError(f"alert_id 必须为正整数，收到: {alert_id}")
        window_minutes = _validate_positive_int(window_minutes, "window_minutes", max_val=1440)
    except ValueError as exc:
        logger.warning("get_alert_context 参数校验失败: %s", exc)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    logger.info("get_alert_context: alert_id=%d window_minutes=%d", alert_id, window_minutes)

    try:
        db = get_db()
    except sqlite3.Error as exc:
        logger.error("数据库连接失败: %s", exc)
        return json.dumps({"error": f"数据库连接失败: {exc}"}, ensure_ascii=False)

    try:
        # 1. 查询目标告警
        target = db.execute("SELECT * FROM alerts WHERE id = ?", [alert_id]).fetchone()
        if not target:
            logger.info("告警 %d 未找到", alert_id)
            return json.dumps(
                {"error": f"Alert {alert_id} not found"}, ensure_ascii=False
            )

        target_dict = dict(target)
        created_at = target_dict["created_at"]

        # 2. 获取时间窗口内的所有告警（排除自身）
        context_alerts_rows = db.execute(
            """SELECT * FROM alerts
               WHERE id != ?
                 AND created_at >= datetime(?, ?)
                 AND created_at <= datetime(?, ?)
               ORDER BY created_at""",
            [
                alert_id,
                created_at,
                f"-{window_minutes} minutes",
                created_at,
                f"+{window_minutes} minutes",
            ],
        ).fetchall()

        # 3. 获取相同 src_ip 或 dst_ip 的原始事件
        raw_events_rows = []
        ip_conditions = []
        ip_params: list = [created_at, f"-{window_minutes} minutes",
                           created_at, f"+{window_minutes} minutes"]

        if target_dict.get("src_ip"):
            ip_conditions.append("raw_json LIKE ?")
            ip_params.append(f"%{target_dict['src_ip']}%")
        if target_dict.get("dst_ip"):
            ip_conditions.append("raw_json LIKE ?")
            ip_params.append(f"%{target_dict['dst_ip']}%")

        if ip_conditions:
            raw_query = (
                "SELECT * FROM raw_events"
                " WHERE received_at >= datetime(?, ?)"
                "   AND received_at <= datetime(?, ?)"
                f"  AND ({' OR '.join(ip_conditions)})"
                " ORDER BY received_at"
            )
            raw_events_rows = db.execute(raw_query, ip_params).fetchall()

        result = {
            "target_alert": target_dict,
            "context_alerts": [dict(r) for r in context_alerts_rows],
            "raw_events": [dict(r) for r in raw_events_rows],
        }
        logger.info(
            "get_alert_context: 找到 %d 条上下文告警, %d 条原始事件",
            len(result["context_alerts"]),
            len(result["raw_events"]),
        )
        return json.dumps(result, ensure_ascii=False, default=str)
    except sqlite3.Error as exc:
        logger.error("查询告警上下文失败: %s", exc)
        return json.dumps({"error": f"查询失败: {exc}"}, ensure_ascii=False)
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
