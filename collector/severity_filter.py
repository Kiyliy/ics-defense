"""
分级过滤模块

按严重级别过滤告警，决定是否进入 Agent 分析流程。
"""


class SeverityFilter:
    """按严重级别过滤告警"""
    AGENT_LEVELS = {"critical", "error"}  # 进入 Agent 分析的级别
    STORE_ONLY_LEVELS = {"warning", "info"}  # 仅存储的级别

    @staticmethod
    def should_analyze(severity: str) -> bool:
        """是否应该进入 Agent 分析"""
        return severity.lower() in SeverityFilter.AGENT_LEVELS

    @staticmethod
    def filter_for_agent(alerts: list[dict]) -> tuple[list[dict], list[dict]]:
        """将告警分为两组: (需分析的, 仅存储的)"""
        to_analyze = []
        store_only = []
        for alert in alerts:
            severity = alert.get("severity", "info").lower()
            if severity in SeverityFilter.AGENT_LEVELS:
                to_analyze.append(alert)
            else:
                store_only.append(alert)
        return to_analyze, store_only
