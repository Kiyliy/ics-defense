import json
import re
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="rule-engine", instructions="ICS 安全关联规则匹配引擎")

# 预定义关联规则
CORRELATION_RULES = [
    {
        "id": "rule-port-scan-then-exploit",
        "name": "端口扫描后利用",
        "description": "同一源IP先进行端口扫描，后发起漏洞利用",
        "conditions": {
            "same_field": "src_ip",
            "sequence": [
                {"title_pattern": "端口扫描|port scan|nmap", "within_hours": 24},
                {"title_pattern": "漏洞利用|exploit|注入|injection", "within_hours": 24},
            ],
        },
        "risk_boost": "high",
        "mitre_chain": ["T0846", "T0866"],
    },
    {
        "id": "rule-brute-force",
        "name": "暴力破解",
        "description": "同一源IP短时间内大量登录失败",
        "conditions": {
            "same_field": "src_ip",
            "title_pattern": "登录失败|login fail|authentication fail|brute",
            "min_count": 10,
            "within_hours": 1,
        },
        "risk_boost": "high",
        "mitre_chain": ["T0078"],
    },
    {
        "id": "rule-sql-injection-chain",
        "name": "SQL注入攻击链",
        "description": "SQL注入告警且目标为关键资产",
        "conditions": {
            "title_pattern": "SQL注入|sql injection|sqli",
            "min_count": 5,
        },
        "risk_boost": "critical",
        "mitre_chain": ["T0890"],
    },
    {
        "id": "rule-lateral-movement",
        "name": "横向移动",
        "description": "内网IP之间的异常连接",
        "conditions": {
            "src_ip_pattern": r"^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)",
            "dst_ip_pattern": r"^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)",
            "title_pattern": "异常连接|lateral|远程执行|remote exec",
        },
        "risk_boost": "high",
        "mitre_chain": ["T0812"],
    },
    {
        "id": "rule-data-exfiltration",
        "name": "数据外泄",
        "description": "内网IP向外网发送大量数据",
        "conditions": {
            "src_ip_pattern": r"^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)",
            "dst_ip_pattern": r"^(?!(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.))",
            "title_pattern": "数据外泄|exfiltration|大量传输|异常流量",
        },
        "risk_boost": "critical",
        "mitre_chain": ["T0882"],
    },
]


def _matches_title(alert: dict, pattern: str) -> bool:
    """Check if alert title matches the given regex pattern (case-insensitive)."""
    title = alert.get("title", "")
    return bool(re.search(pattern, title, re.IGNORECASE))


def _matches_ip(value: str | None, pattern: str) -> bool:
    """Check if an IP value matches the given regex pattern."""
    if not value:
        return False
    return bool(re.search(pattern, value))


def _check_rule(rule: dict, alerts: list) -> dict | None:
    """检查单条规则是否匹配。

    根据 conditions 中的字段进行匹配:
    - title_pattern: 正则匹配告警 title
    - same_field: 要求告警的某字段值相同（按字段值分组后判断）
    - min_count: 最少告警数
    - src_ip_pattern / dst_ip_pattern: IP 正则
    - sequence: 按顺序出现的告警模式
    """
    conditions = rule["conditions"]

    # --- sequence-based rules (e.g., port-scan-then-exploit) ---
    if "sequence" in conditions:
        return _check_sequence_rule(rule, alerts)

    # --- non-sequence rules ---
    # First, filter alerts by title_pattern and IP patterns
    title_pat = conditions.get("title_pattern")
    src_ip_pat = conditions.get("src_ip_pattern")
    dst_ip_pat = conditions.get("dst_ip_pattern")

    filtered = []
    for a in alerts:
        if title_pat and not _matches_title(a, title_pat):
            continue
        if src_ip_pat and not _matches_ip(a.get("src_ip"), src_ip_pat):
            continue
        if dst_ip_pat and not _matches_ip(a.get("dst_ip"), dst_ip_pat):
            continue
        filtered.append(a)

    if not filtered:
        return None

    same_field = conditions.get("same_field")
    min_count = conditions.get("min_count", 1)

    if same_field:
        # Group by the same_field value and check each group
        groups: dict[str, list] = {}
        for a in filtered:
            key = a.get(same_field, "")
            if key:
                groups.setdefault(key, []).append(a)

        # Find the first group meeting min_count
        for key, group in groups.items():
            if len(group) >= min_count:
                return {
                    "rule": _rule_info(rule),
                    "matched_alerts": group,
                    "evidence": (
                        f"共 {len(group)} 条告警匹配，"
                        f"{same_field}={key}"
                    ),
                }
        return None
    else:
        if len(filtered) >= min_count:
            return {
                "rule": _rule_info(rule),
                "matched_alerts": filtered,
                "evidence": f"共 {len(filtered)} 条告警匹配规则 [{rule['name']}]",
            }
        return None


def _check_sequence_rule(rule: dict, alerts: list) -> dict | None:
    """Check a sequence-based rule where alerts must appear in order."""
    conditions = rule["conditions"]
    same_field = conditions.get("same_field")
    sequence = conditions["sequence"]

    if not same_field:
        return None

    # Group alerts by the same_field
    groups: dict[str, list] = {}
    for a in alerts:
        key = a.get(same_field, "")
        if key:
            groups.setdefault(key, []).append(a)

    for key, group in groups.items():
        # Try to find the sequence in order
        matched_alerts = []
        seq_idx = 0
        for a in group:
            if seq_idx >= len(sequence):
                break
            step = sequence[seq_idx]
            if _matches_title(a, step["title_pattern"]):
                matched_alerts.append(a)
                seq_idx += 1

        if seq_idx == len(sequence):
            return {
                "rule": _rule_info(rule),
                "matched_alerts": matched_alerts,
                "evidence": (
                    f"检测到攻击序列：{same_field}={key}，"
                    f"匹配 {len(sequence)} 个阶段"
                ),
            }

    return None


def _rule_info(rule: dict) -> dict:
    """Extract public rule info (without internal conditions)."""
    return {
        "id": rule["id"],
        "name": rule["name"],
        "description": rule["description"],
        "risk_boost": rule["risk_boost"],
        "mitre_chain": rule["mitre_chain"],
    }


@mcp.tool()
def match_rules(alerts: list[dict] | str) -> str:
    """对一组告警执行关联规则匹配

    Args:
        alerts: 告警数组；优先直接传结构化数组，也兼容 JSON 字符串

    Returns:
        JSON: {"matched_rules": [{"rule": {...}, "matched_alerts": [...], "evidence": "..."}]}
    """
    if isinstance(alerts, str):
        alerts = json.loads(alerts)
    matched = []
    for rule in CORRELATION_RULES:
        result = _check_rule(rule, alerts)
        if result:
            matched.append(result)
    return json.dumps({"matched_rules": matched}, ensure_ascii=False)


@mcp.tool()
def get_rules() -> str:
    """查询当前所有关联规则

    Returns:
        JSON 格式的规则列表（不含内部匹配逻辑）
    """
    rules_info = []
    for r in CORRELATION_RULES:
        rules_info.append(
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "risk_boost": r["risk_boost"],
                "mitre_chain": r["mitre_chain"],
            }
        )
    return json.dumps({"rules": rules_info}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
