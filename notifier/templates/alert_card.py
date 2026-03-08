"""通知消息模板。

提供多种事件类型的消息格式化函数，返回 (title, content) 元组。
内容使用 Markdown 格式，适用于支持 Markdown 的渠道（如飞书卡片）。
"""

import time
from typing import Optional

# 严重等级中文映射
_LEVEL_LABELS: dict[str, str] = {
    "critical": "严重",
    "high": "高危",
    "medium": "中等",
    "low": "低危",
    "info": "信息",
}


def _timestamp() -> str:
    """返回当前时间字符串。"""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def format_alert_notification(alert: dict) -> tuple[str, str]:
    """格式化安全告警通知。

    Args:
        alert: 告警数据字典，期望包含以下字段:
            - alert_type (str): 告警类型。
            - level (str): 严重等级。
            - source (str): 告警来源。
            - description (str): 告警描述。
            - target (str, 可选): 受影响目标。
            - recommendation (str, 可选): 处置建议。

    Returns:
        (title, content) 元组。
    """
    alert_type = alert.get("alert_type", "未知告警")
    level = alert.get("level", "info")
    level_label = _LEVEL_LABELS.get(level, level)
    source = alert.get("source", "未知")
    description = alert.get("description", "无详细描述")
    target = alert.get("target", "")
    recommendation = alert.get("recommendation", "")

    title = f"安全告警: {alert_type}"

    lines = [
        f"**告警等级:** {level_label}",
        f"**告警来源:** {source}",
        f"**告警时间:** {_timestamp()}",
        "",
        f"**描述:** {description}",
    ]
    if target:
        lines.append(f"**受影响目标:** {target}")
    if recommendation:
        lines.append("")
        lines.append(f"**处置建议:** {recommendation}")

    content = "\n".join(lines)
    return title, content


def format_decision_notification(decision: dict) -> tuple[str, str]:
    """格式化智能体决策通知。

    Args:
        decision: 决策数据字典，期望包含以下字段:
            - agent_name (str): 智能体名称。
            - action (str): 执行动作。
            - reason (str): 决策原因。
            - confidence (float, 可选): 置信度。
            - affected_assets (list[str], 可选): 受影响资产列表。

    Returns:
        (title, content) 元组。
    """
    agent_name = decision.get("agent_name", "未知智能体")
    action = decision.get("action", "未知动作")
    reason = decision.get("reason", "")
    confidence = decision.get("confidence")
    affected = decision.get("affected_assets", [])

    title = f"智能体决策: {agent_name}"

    lines = [
        f"**智能体:** {agent_name}",
        f"**执行动作:** {action}",
        f"**决策时间:** {_timestamp()}",
    ]
    if confidence is not None:
        lines.append(f"**置信度:** {confidence:.1%}")
    if reason:
        lines.append("")
        lines.append(f"**决策原因:** {reason}")
    if affected:
        lines.append("")
        lines.append("**受影响资产:**")
        for asset in affected:
            lines.append(f"- {asset}")

    content = "\n".join(lines)
    return title, content


def format_approval_notification(approval: dict) -> tuple[str, str]:
    """格式化审批请求通知。

    Args:
        approval: 审批数据字典，期望包含以下字段:
            - request_id (str): 审批请求 ID。
            - action (str): 待审批动作。
            - requester (str): 请求者。
            - reason (str): 请求原因。
            - urgency (str, 可选): 紧急程度。
            - deadline (str, 可选): 审批截止时间。

    Returns:
        (title, content) 元组。
    """
    request_id = approval.get("request_id", "N/A")
    action = approval.get("action", "未知操作")
    requester = approval.get("requester", "未知")
    reason = approval.get("reason", "")
    urgency = approval.get("urgency", "普通")
    deadline = approval.get("deadline", "")

    title = f"审批请求: {action}"

    lines = [
        f"**请求 ID:** {request_id}",
        f"**请求操作:** {action}",
        f"**请求者:** {requester}",
        f"**紧急程度:** {urgency}",
        f"**请求时间:** {_timestamp()}",
    ]
    if deadline:
        lines.append(f"**审批截止:** {deadline}")
    if reason:
        lines.append("")
        lines.append(f"**请求原因:** {reason}")
    lines.append("")
    lines.append("请及时处理此审批请求。")

    content = "\n".join(lines)
    return title, content


def format_error_notification(error: dict) -> tuple[str, str]:
    """格式化系统错误通知。

    Args:
        error: 错误数据字典，期望包含以下字段:
            - error_type (str): 错误类型。
            - message (str): 错误消息。
            - component (str, 可选): 出错组件。
            - traceback (str, 可选): 堆栈跟踪。
            - severity (str, 可选): 严重程度。

    Returns:
        (title, content) 元组。
    """
    error_type = error.get("error_type", "未知错误")
    message = error.get("message", "无错误详情")
    component = error.get("component", "")
    traceback_str = error.get("traceback", "")
    severity = error.get("severity", "high")
    severity_label = _LEVEL_LABELS.get(severity, severity)

    title = f"系统错误: {error_type}"

    lines = [
        f"**错误类型:** {error_type}",
        f"**严重程度:** {severity_label}",
        f"**发生时间:** {_timestamp()}",
    ]
    if component:
        lines.append(f"**出错组件:** {component}")
    lines.append("")
    lines.append(f"**错误信息:** {message}")
    if traceback_str:
        lines.append("")
        lines.append("**堆栈跟踪:**")
        lines.append(f"```\n{traceback_str}\n```")

    content = "\n".join(lines)
    return title, content
