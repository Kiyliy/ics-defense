"""通知模块（notifier）。

提供多渠道通知能力，支持飞书、通用 Webhook、邮件等渠道。

用法::

    from notifier import NotificationManager

    manager = NotificationManager.from_env()
    await manager.notify("alert", {
        "alert_type": "入侵检测",
        "level": "high",
        "source": "Suricata",
        "description": "检测到可疑的 Modbus 写入操作",
    })
"""

from .manager import NotificationManager

__all__ = ["NotificationManager"]
