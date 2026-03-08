import json
import os
import sqlite3
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="log-search", instructions="ICS 安全告警和日志查询服务")

# 数据库路径通过环境变量配置
DB_PATH = os.environ.get("ICS_DB_PATH") or os.environ.get("DB_PATH") or "backend/data/ics-defense.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    db = get_db()
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
    db.close()
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


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
    db = get_db()
    query = "SELECT * FROM raw_events WHERE received_at >= datetime('now', ?)"
    params: list = [f"-{hours} hours"]

    if source:
        query += " AND source = ?"
        params.append(source)

    query += " ORDER BY received_at DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(query, params).fetchall()
    db.close()
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


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
    db = get_db()

    # 1. 查询目标告警
    target = db.execute("SELECT * FROM alerts WHERE id = ?", [alert_id]).fetchone()
    if not target:
        db.close()
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

    db.close()

    return json.dumps(
        {
            "target_alert": target_dict,
            "context_alerts": [dict(r) for r in context_alerts_rows],
            "raw_events": [dict(r) for r in raw_events_rows],
        },
        ensure_ascii=False,
        default=str,
    )


if __name__ == "__main__":
    mcp.run()
