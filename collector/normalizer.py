"""
多源事件规范化服务

将来自不同安全设备的原始日志统一为标准告警格式。
支持的数据源：WAF（雷池）、NIDS（Suricata）、HIDS（Wazuh）、PIKACHU 靶场、SOC 日志
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional
import json


# MITRE ATT&CK for ICS 战术映射（简化版）
TACTIC_KEYWORDS = {
    "scan": {"tactic": "Reconnaissance", "technique": "T0846"},
    "brute": {"tactic": "Initial Access", "technique": "T0866"},
    "login": {"tactic": "Initial Access", "technique": "T0078"},
    "injection": {"tactic": "Execution", "technique": "T0807"},
    "xss": {"tactic": "Execution", "technique": "T0807"},
    "sql": {"tactic": "Execution", "technique": "T0807"},
    "rce": {"tactic": "Execution", "technique": "T0807"},
    "upload": {"tactic": "Persistence", "technique": "T0839"},
    "shell": {"tactic": "Execution", "technique": "T0807"},
    "privilege": {"tactic": "Privilege Escalation", "technique": "T0890"},
    "exfiltration": {"tactic": "Exfiltration", "technique": "T0882"},
    "c2": {"tactic": "Command and Control", "technique": "T0869"},
    "dos": {"tactic": "Impact", "technique": "T0814"},
}


def _infer_mitre(text: str) -> dict:
    """根据告警标题/描述推断 MITRE ATT&CK 映射"""
    lower = (text or "").lower()
    for keyword, mapping in TACTIC_KEYWORDS.items():
        if keyword in lower:
            return mapping
    return {"tactic": "Unknown", "technique": None}


def _normalize_severity_waf(raw_severity: str) -> str:
    """WAF severity 映射: 严重→critical, 高→error, 中→warning, 低→info"""
    s = str(raw_severity or "").lower()
    if any(k in s for k in ["critical", "crit", "严重", "4", "5"]):
        return "critical"
    if any(k in s for k in ["high", "高", "3"]):
        return "error"
    if any(k in s for k in ["medium", "med", "中", "2"]):
        return "warning"
    return "info"


def _normalize_severity_nids(severity_value) -> str:
    """Suricata severity 映射: 1→critical, 2→error, 3→warning, 其他→info"""
    try:
        level = int(severity_value)
    except (TypeError, ValueError):
        return "info"
    if level == 1:
        return "critical"
    elif level == 2:
        return "error"
    elif level == 3:
        return "warning"
    return "info"


def _normalize_severity_hids(level_value) -> str:
    """Wazuh level 映射: >=12→critical, >=8→error, >=4→warning, <4→info"""
    try:
        level = int(level_value)
    except (TypeError, ValueError):
        return "info"
    if level >= 12:
        return "critical"
    elif level >= 8:
        return "error"
    elif level >= 4:
        return "warning"
    return "info"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NormalizedAlert:
    """统一告警格式"""
    source: str              # waf | nids | hids | pikachu | soc
    title: str               # 告警标题
    description: str         # 告警描述
    severity: str            # critical | error | warning | info
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None
    raw_json: Optional[str] = None      # 原始 JSON 字符串
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    timestamp: str = ""      # ISO 格式

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_waf(raw: dict) -> NormalizedAlert:
    """雷池 WAF 日志规范化
    典型字段: rule_name, severity, src_ip, dst_ip, url, payload
    severity 映射: 严重→critical, 高→error, 中→warning, 低→info
    """
    title = raw.get("rule_name") or raw.get("event_type") or "WAF Alert"
    mitre = _infer_mitre(title)
    return NormalizedAlert(
        source="waf",
        title=title,
        description=raw.get("reason") or raw.get("detail") or json.dumps(raw, ensure_ascii=False),
        severity=_normalize_severity_waf(raw.get("severity") or raw.get("risk_level")),
        src_ip=raw.get("src_ip") or raw.get("remote_addr"),
        dst_ip=raw.get("dst_ip") or raw.get("server_addr"),
        src_port=raw.get("src_port"),
        dst_port=raw.get("dst_port"),
        protocol=raw.get("protocol"),
        raw_json=json.dumps(raw, ensure_ascii=False),
        mitre_tactic=mitre["tactic"],
        mitre_technique=mitre["technique"],
        timestamp=raw.get("timestamp") or _now_iso(),
    )


def normalize_nids(raw: dict) -> NormalizedAlert:
    """Suricata NIDS 告警规范化
    典型字段: alert.signature, alert.severity, src_ip, dest_ip, proto
    severity 映射: 1→critical, 2→error, 3→warning, 其他→info
    """
    alert = raw.get("alert") or {}
    title = alert.get("signature") or "NIDS Alert"
    description = f"SID:{alert.get('signature_id')} Category:{alert.get('category') or 'N/A'}"
    mitre = _infer_mitre(alert.get("signature") or alert.get("category") or "")
    return NormalizedAlert(
        source="nids",
        title=title,
        description=description,
        severity=_normalize_severity_nids(alert.get("severity")),
        src_ip=raw.get("src_ip"),
        dst_ip=raw.get("dest_ip") or raw.get("dst_ip"),
        src_port=raw.get("src_port"),
        dst_port=raw.get("dest_port") or raw.get("dst_port"),
        protocol=raw.get("proto"),
        raw_json=json.dumps(raw, ensure_ascii=False),
        mitre_tactic=mitre["tactic"],
        mitre_technique=mitre["technique"],
        timestamp=raw.get("timestamp") or _now_iso(),
    )


def normalize_hids(raw: dict) -> NormalizedAlert:
    """Wazuh HIDS 告警规范化
    典型字段: rule.id, rule.description, rule.level, agent.ip
    level 映射: >=12→critical, >=8→error, >=4→warning, <4→info
    """
    rule = raw.get("rule") or {}
    agent = raw.get("agent") or {}
    data = raw.get("data") or {}
    title = rule.get("description") or "HIDS Alert"
    groups = rule.get("groups") or []
    description = f"Rule:{rule.get('id')} Groups:{','.join(groups)}"
    mitre = _infer_mitre(title)
    return NormalizedAlert(
        source="hids",
        title=title,
        description=description,
        severity=_normalize_severity_hids(rule.get("level")),
        src_ip=data.get("srcip") or agent.get("ip"),
        dst_ip=agent.get("ip"),
        src_port=raw.get("src_port"),
        dst_port=raw.get("dst_port"),
        protocol=raw.get("protocol"),
        raw_json=json.dumps(raw, ensure_ascii=False),
        mitre_tactic=mitre["tactic"],
        mitre_technique=mitre["technique"],
        timestamp=raw.get("timestamp") or _now_iso(),
    )


def normalize_pikachu(raw: dict) -> NormalizedAlert:
    """PIKACHU 靶场日志规范化
    典型字段: vul_type, payload, src_ip, target
    所有 pikachu 告警默认 severity=warning
    """
    title = raw.get("vuln_type") or raw.get("vul_type") or raw.get("title") or "Pikachu Alert"
    mitre = _infer_mitre(title)
    return NormalizedAlert(
        source="pikachu",
        title=title,
        description=raw.get("payload") or raw.get("detail") or json.dumps(raw, ensure_ascii=False),
        severity="warning",
        src_ip=raw.get("src_ip") or raw.get("attacker_ip"),
        dst_ip=raw.get("dst_ip") or raw.get("target_ip"),
        src_port=raw.get("src_port"),
        dst_port=raw.get("dst_port"),
        protocol=raw.get("protocol"),
        raw_json=json.dumps(raw, ensure_ascii=False),
        mitre_tactic=mitre["tactic"],
        mitre_technique=mitre["technique"],
        timestamp=raw.get("timestamp") or _now_iso(),
    )


def normalize_soc(raw: dict) -> NormalizedAlert:
    """SOC 通用日志规范化
    尝试从 raw 中提取通用字段
    """
    title = raw.get("title") or raw.get("message") or "Generic Alert"
    mitre = _infer_mitre(title)
    return NormalizedAlert(
        source=raw.get("source") or "soc",
        title=title,
        description=raw.get("description") or json.dumps(raw, ensure_ascii=False),
        severity=_normalize_severity_waf(raw.get("severity")),
        src_ip=raw.get("src_ip"),
        dst_ip=raw.get("dst_ip"),
        src_port=raw.get("src_port"),
        dst_port=raw.get("dst_port"),
        protocol=raw.get("protocol"),
        raw_json=json.dumps(raw, ensure_ascii=False),
        mitre_tactic=mitre["tactic"],
        mitre_technique=mitre["technique"],
        timestamp=raw.get("timestamp") or _now_iso(),
    )


def normalize(source: str, raw: dict) -> NormalizedAlert:
    """根据 source 分派到对应的规范化函数"""
    normalizers = {
        "waf": normalize_waf,
        "nids": normalize_nids,
        "hids": normalize_hids,
        "pikachu": normalize_pikachu,
        "soc": normalize_soc,
    }
    fn = normalizers.get(source, normalize_soc)
    return fn(raw)
