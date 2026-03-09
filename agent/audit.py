"""
Agent 审计日志记录器 — 使用统一数据层记录 Agent 所有行为。
"""

import json
import sqlite3
from datetime import datetime, timedelta

from agent.db import get_db, init_db


class AuditLogger:
    """Agent 审计日志记录器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        # Ensure tables exist (idempotent)
        init_db(db_path)

    def close(self):
        """关闭数据库连接（保留接口兼容性）"""
        # Connection lifecycle is now managed by agent.db per-thread pool.
        pass

    def log(
        self,
        trace_id: str,
        event_type: str,
        data: dict,
        alert_id: str = None,
        token_usage: dict = None,
    ):
        """写入一条审计日志"""
        with get_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (trace_id, alert_id, event_type, data, token_usage)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    alert_id,
                    event_type,
                    json.dumps(data, ensure_ascii=False) if data else None,
                    json.dumps(token_usage, ensure_ascii=False)
                    if token_usage
                    else None,
                ),
            )
            conn.commit()

    def get_trace(self, trace_id: str) -> list:
        """按 trace_id 查询完整审计链，按时间排序"""
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, trace_id, alert_id, event_type, data, token_usage, created_at
                FROM audit_logs
                WHERE trace_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (trace_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_by_alert(self, alert_id: str) -> list:
        """按 alert_id 查询相关审计日志"""
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, trace_id, alert_id, event_type, data, token_usage, created_at
                FROM audit_logs
                WHERE alert_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (alert_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_total_tokens(self, trace_id: str) -> dict:
        """汇总某次分析的 token 用量"""
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT token_usage FROM audit_logs
                WHERE trace_id = ? AND token_usage IS NOT NULL
                """,
                (trace_id,),
            ).fetchall()

        total_input = 0
        total_output = 0
        for row in rows:
            usage = json.loads(row["token_usage"])
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)

        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total": total_input + total_output,
        }

    def get_stats(self, days: int = 7) -> dict:
        """统计最近 N 天的 token 用量和分析次数"""
        cutoff = (datetime.now(tz=None) - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        with get_db(self.db_path) as conn:
            # 总分析次数（不同的 trace_id 数量）
            row = conn.execute(
                """
                SELECT COUNT(DISTINCT trace_id) as cnt
                FROM audit_logs
                WHERE created_at >= ?
                """,
                (cutoff,),
            ).fetchone()
            total_analyses = row["cnt"] if row else 0

            # 总 token
            rows = conn.execute(
                """
                SELECT token_usage FROM audit_logs
                WHERE created_at >= ? AND token_usage IS NOT NULL
                """,
                (cutoff,),
            ).fetchall()

            total_tokens = 0
            for r in rows:
                usage = json.loads(r["token_usage"])
                total_tokens += usage.get("input_tokens", 0) + usage.get(
                    "output_tokens", 0
                )

            # 每日统计
            daily_rows = conn.execute(
                """
                SELECT DATE(created_at) as day,
                       COUNT(DISTINCT trace_id) as analyses,
                       COUNT(*) as events
                FROM audit_logs
                WHERE created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY day ASC
                """,
                (cutoff,),
            ).fetchall()

            daily = []
            for dr in daily_rows:
                day_token_rows = conn.execute(
                    """
                    SELECT token_usage FROM audit_logs
                    WHERE DATE(created_at) = ? AND token_usage IS NOT NULL
                    """,
                    (dr["day"],),
                ).fetchall()
                day_tokens = 0
                for tr in day_token_rows:
                    usage = json.loads(tr["token_usage"])
                    day_tokens += usage.get("input_tokens", 0) + usage.get(
                        "output_tokens", 0
                    )
                daily.append(
                    {
                        "date": dr["day"],
                        "analyses": dr["analyses"],
                        "events": dr["events"],
                        "tokens": day_tokens,
                    }
                )

        return {
            "total_analyses": total_analyses,
            "total_tokens": total_tokens,
            "daily": daily,
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        if d.get("data"):
            d["data"] = json.loads(d["data"])
        if d.get("token_usage"):
            d["token_usage"] = json.loads(d["token_usage"])
        return d
