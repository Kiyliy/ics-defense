"""通知模板子包。

导出所有模板格式化函数。
"""

from .alert_card import (
    format_alert_notification,
    format_approval_notification,
    format_decision_notification,
    format_error_notification,
)

__all__ = [
    "format_alert_notification",
    "format_approval_notification",
    "format_decision_notification",
    "format_error_notification",
]
