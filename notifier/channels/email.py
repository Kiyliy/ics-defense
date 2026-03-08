"""邮件通知渠道（SMTP）。

使用 aiosmtplib 异步发送 HTML 格式的通知邮件。
"""

import logging
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .base import BaseNotificationChannel

logger = logging.getLogger(__name__)

# 严重等级 -> 样式颜色
_LEVEL_STYLES: dict[str, dict[str, str]] = {
    "critical": {"bg": "#DC3545", "fg": "#FFFFFF", "label": "严重"},
    "high": {"bg": "#FD7E14", "fg": "#FFFFFF", "label": "高危"},
    "medium": {"bg": "#FFC107", "fg": "#000000", "label": "中等"},
    "low": {"bg": "#28A745", "fg": "#FFFFFF", "label": "低危"},
    "info": {"bg": "#17A2B8", "fg": "#FFFFFF", "label": "信息"},
}


def _build_html(
    title: str,
    content: str,
    level: str,
    metadata: Optional[dict],
) -> str:
    """构建 HTML 邮件正文。

    Args:
        title: 邮件标题。
        content: 邮件正文。
        level: 严重等级。
        metadata: 附加元数据。

    Returns:
        HTML 字符串。
    """
    style = _LEVEL_STYLES.get(level, _LEVEL_STYLES["info"])
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # 将纯文本换行转为 HTML 段落
    content_html = content.replace("\n", "<br/>")

    meta_rows = ""
    if metadata:
        for key, value in metadata.items():
            meta_rows += (
                f'<tr><td style="padding:4px 8px;font-weight:bold;">{key}</td>'
                f'<td style="padding:4px 8px;">{value}</td></tr>'
            )

    meta_section = ""
    if meta_rows:
        meta_section = f"""
        <h3 style="margin-top:16px;">附加信息</h3>
        <table border="1" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;border-color:#ddd;">
            {meta_rows}
        </table>
        """

    html = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;">
  <div style="max-width:600px;margin:20px auto;border:1px solid #ddd;border-radius:8px;overflow:hidden;">
    <!-- 标题栏 -->
    <div style="background:{style['bg']};color:{style['fg']};padding:16px 20px;">
      <h2 style="margin:0;">{title}</h2>
      <span style="font-size:12px;">等级: {style['label']} | {timestamp}</span>
    </div>
    <!-- 正文 -->
    <div style="padding:20px;">
      <p>{content_html}</p>
      {meta_section}
    </div>
    <!-- 页脚 -->
    <div style="background:#f5f5f5;padding:10px 20px;font-size:12px;color:#888;text-align:center;">
      ICS Defense 安全通知系统
    </div>
  </div>
</body>
</html>
"""
    return html


class EmailChannel(BaseNotificationChannel):
    """邮件通知渠道。

    通过 SMTP 异步发送 HTML 格式的通知邮件。

    Args:
        smtp_host: SMTP 服务器地址。
        smtp_port: SMTP 端口，默认 587（STARTTLS）。
        username: SMTP 认证用户名。
        password: SMTP 认证密码。
        from_addr: 发件人地址。
        to_addrs: 收件人地址列表。
        use_tls: 是否使用 STARTTLS，默认 True。
    """

    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        to_addrs: Optional[list[str]] = None,
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host.strip()
        self.smtp_port = smtp_port
        self.username = username.strip()
        self.password = password
        self.from_addr = from_addr.strip()
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    def is_configured(self) -> bool:
        """检查邮件渠道是否已配置。"""
        return bool(
            self.smtp_host
            and self.from_addr
            and self.to_addrs
        )

    async def send(
        self,
        title: str,
        content: str,
        level: str = "info",
        metadata: Optional[dict] = None,
    ) -> bool:
        """通过邮件发送通知。

        Args:
            title: 邮件主题。
            content: 邮件正文。
            level: 严重等级。
            metadata: 附加元数据。

        Returns:
            发送成功返回 True。
        """
        if not self.is_configured():
            logger.warning("邮件渠道未配置，跳过发送")
            return False

        try:
            import aiosmtplib
        except ImportError:
            logger.error("未安装 aiosmtplib，无法发送邮件。请执行: pip install aiosmtplib")
            return False

        html = _build_html(title, content, level, metadata)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[ICS Defense] {title}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.attach(MIMEText(content, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.username or None,
                password=self.password or None,
                start_tls=self.use_tls,
            )
            logger.info("邮件发送成功: %s -> %s", title, self.to_addrs)
            return True

        except Exception as exc:
            logger.error("邮件发送异常: %s", exc)
            return False
