"""
日志聚簇模块

相同日志合并为一条 + 计数，在时间窗口内将相同特征的告警合并。
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict


def _parse_timestamp(value: str | None) -> datetime | None:
    """解析 ISO 时间戳；无法解析时返回 None。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class ClusteredAlert:
    """聚簇后的告警"""
    signature: str           # 聚簇键（hash）
    sample: dict             # 一条完整的样本告警
    count: int = 1
    first_seen: str = ""
    last_seen: str = ""
    severity: str = "low"
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
        self._flushed: list[ClusteredAlert] = []  # clusters flushed due to window overflow

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

    def _is_expired(self, cluster: ClusteredAlert) -> bool:
        """Check if a cluster's last_seen is older than window_seconds ago."""
        last_dt = _parse_timestamp(cluster.last_seen)
        if last_dt is None:
            return False
        now = datetime.now(timezone.utc)
        return (now - last_dt) > timedelta(seconds=self.window)

    def _exceeds_window(self, cluster: ClusteredAlert, now_dt: datetime | None) -> bool:
        """Check if the time span from first_seen to now_dt exceeds window_seconds."""
        if now_dt is None:
            return False
        first_dt = _parse_timestamp(cluster.first_seen)
        if first_dt is None:
            return False
        return (now_dt - first_dt).total_seconds() > self.window

    def add(self, alert: dict) -> str:
        """添加一条告警到聚簇器，返回 signature"""
        sig = self._compute_signature(alert)
        now = alert.get("timestamp") or datetime.now(timezone.utc).isoformat()
        now_dt = _parse_timestamp(now)

        if sig in self.clusters:
            cluster = self.clusters[sig]

            # If the new alert would exceed the time window, flush the old
            # cluster and start a fresh one with the same signature.
            if self._exceeds_window(cluster, now_dt):
                # Move old cluster to _flushed so flush_expired can return it
                self._flushed.append(cluster)
                self.clusters[sig] = ClusteredAlert(
                    signature=sig,
                    sample=alert,
                    count=1,
                    first_seen=now,
                    last_seen=now,
                    severity=alert.get("severity", "low"),
                    source_ips=[alert["src_ip"]] if alert.get("src_ip") else [],
                    target_ips=[alert["dst_ip"]] if alert.get("dst_ip") else [],
                )
                return sig

            cluster.count += 1
            first_dt = _parse_timestamp(cluster.first_seen)
            last_dt = _parse_timestamp(cluster.last_seen)

            if first_dt is None or (now_dt is not None and now_dt < first_dt):
                cluster.first_seen = now
            if last_dt is None or (now_dt is not None and now_dt > last_dt):
                cluster.last_seen = now

            # 收集去重的 IP
            src_ip = alert.get("src_ip")
            dst_ip = alert.get("dst_ip")
            if src_ip and src_ip not in cluster.source_ips:
                cluster.source_ips.append(src_ip)
            if dst_ip and dst_ip not in cluster.target_ips:
                cluster.target_ips.append(dst_ip)

            severity = alert.get("severity")
            if severity == "critical" and cluster.severity != "critical":
                cluster.severity = severity
        else:
            self.clusters[sig] = ClusteredAlert(
                signature=sig,
                sample=alert,
                count=1,
                first_seen=now,
                last_seen=now,
                severity=alert.get("severity", "low"),
                source_ips=[alert["src_ip"]] if alert.get("src_ip") else [],
                target_ips=[alert["dst_ip"]] if alert.get("dst_ip") else [],
            )

        return sig

    def flush(self) -> list[ClusteredAlert]:
        """返回所有聚簇结果并清空"""
        result = list(self.clusters.values()) + self._flushed
        self.clusters = {}
        self._flushed = []
        return result

    def flush_expired(self) -> list[ClusteredAlert]:
        """Returns and removes clusters whose last_seen is older than window_seconds ago."""
        expired = []
        remaining = {}
        for sig, cluster in self.clusters.items():
            if self._is_expired(cluster):
                expired.append(cluster)
            else:
                remaining[sig] = cluster
        self.clusters = remaining
        # Also return any clusters that were flushed due to window overflow
        expired.extend(self._flushed)
        self._flushed = []
        return expired

    def get_clusters(self) -> list[ClusteredAlert]:
        """返回当前所有聚簇（不清空）"""
        return list(self.clusters.values())
