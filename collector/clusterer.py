"""
日志聚簇模块

相同日志合并为一条 + 计数，在时间窗口内将相同特征的告警合并。
"""

import hashlib
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict


@dataclass
class ClusteredAlert:
    """聚簇后的告警"""
    signature: str           # 聚簇键（hash）
    sample: dict             # 一条完整的样本告警
    count: int = 1
    first_seen: str = ""
    last_seen: str = ""
    severity: str = "info"
    source_ips: list = field(default_factory=list)
    target_ips: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class AlertClusterer:
    """告警聚簇器
    在时间窗口内，将相同特征的告警合并
    """

    def __init__(self, window_seconds: int = 300):
        self.window = window_seconds
        self.clusters: dict[str, ClusteredAlert] = {}  # signature -> ClusteredAlert

    def _compute_signature(self, alert: dict) -> str:
        """计算聚簇签名
        去掉时间戳等变量字段，对剩余字段取 hash
        关键字段: source, title, severity, src_ip, dst_ip
        """
        key_fields = {
            "source": alert.get("source", ""),
            "title": alert.get("title", ""),
            "severity": alert.get("severity", ""),
            "src_ip": alert.get("src_ip", ""),
            "dst_ip": alert.get("dst_ip", ""),
        }
        key_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def add(self, alert: dict) -> str:
        """添加一条告警到聚簇器，返回 signature"""
        sig = self._compute_signature(alert)
        now = alert.get("timestamp") or datetime.now(timezone.utc).isoformat()

        if sig in self.clusters:
            cluster = self.clusters[sig]
            cluster.count += 1
            cluster.last_seen = now
            # 收集去重的 IP
            src_ip = alert.get("src_ip")
            dst_ip = alert.get("dst_ip")
            if src_ip and src_ip not in cluster.source_ips:
                cluster.source_ips.append(src_ip)
            if dst_ip and dst_ip not in cluster.target_ips:
                cluster.target_ips.append(dst_ip)
        else:
            self.clusters[sig] = ClusteredAlert(
                signature=sig,
                sample=alert,
                count=1,
                first_seen=now,
                last_seen=now,
                severity=alert.get("severity", "info"),
                source_ips=[alert["src_ip"]] if alert.get("src_ip") else [],
                target_ips=[alert["dst_ip"]] if alert.get("dst_ip") else [],
            )

        return sig

    def flush(self) -> list[ClusteredAlert]:
        """返回所有聚簇结果并清空"""
        result = list(self.clusters.values())
        self.clusters = {}
        return result

    def get_clusters(self) -> list[ClusteredAlert]:
        """返回当前所有聚簇（不清空）"""
        return list(self.clusters.values())
