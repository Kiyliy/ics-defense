import json
import logging
import os
import re
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("rule-engine")

mcp = FastMCP(name="rule-engine", instructions="ICS 安全关联规则匹配引擎")

# ---------------------------------------------------------------------------
# Load rules from YAML
# ---------------------------------------------------------------------------
_RULES_PATH = Path(__file__).parent / "rules.yaml"


def _load_rules(path: Path = _RULES_PATH) -> list[dict]:
    """Load correlation rules from YAML config file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data.get("rules", [])
        logger.info("从 %s 加载了 %d 条关联规则", path, len(rules))
        # Normalize field names: severity -> risk_boost, mitre_technique -> mitre_chain
        # to keep backward compatibility with the internal matching logic
        for r in rules:
            if "severity" in r and "risk_boost" not in r:
                r["risk_boost"] = r.pop("severity")
            if "mitre_technique" in r and "mitre_chain" not in r:
                r["mitre_chain"] = r.pop("mitre_technique")
        return rules
    except FileNotFoundError:
        logger.error("规则文件不存在: %s，使用空规则集", path)
        return []
    except yaml.YAMLError as exc:
        logger.error("规则文件 YAML 解析失败: %s，使用空规则集", exc)
        return []
    except Exception as exc:
        logger.error("加载规则文件异常: %s，使用空规则集", exc)
        return []


CORRELATION_RULES = _load_rules()


# ---------------------------------------------------------------------------
# Internal matching helpers
# ---------------------------------------------------------------------------
def _matches_title(alert: dict, pattern: str) -> bool:
    """Check if alert title matches the given regex pattern (case-insensitive)."""
    title = alert.get("title", "")
    try:
        return bool(re.search(pattern, title, re.IGNORECASE))
    except re.error as exc:
        logger.warning("正则表达式错误 '%s': %s", pattern, exc)
        return False


def _matches_ip(value: str | None, pattern: str) -> bool:
    """Check if an IP value matches the given regex pattern."""
    if not value:
        return False
    try:
        return bool(re.search(pattern, value))
    except re.error as exc:
        logger.warning("IP正则表达式错误 '%s': %s", pattern, exc)
        return False


def _check_rule(rule: dict, alerts: list) -> dict | None:
    """检查单条规则是否匹配。

    根据 conditions 中的字段进行匹配:
    - title_pattern: 正则匹配告警 title
    - same_field: 要求告警的某字段值相同（按字段值分组后判断）
    - min_count: 最少告警数
    - src_ip_pattern / dst_ip_pattern: IP 正则
    - sequence: 按顺序出现的告警模式
    """
    conditions = rule.get("conditions")
    if not conditions:
        logger.warning("规则 %s 缺少 conditions 字段", rule.get("id", "?"))
        return None

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
    """Check a sequence-based rule where alerts must appear in order.

    Also validates the ``within_hours`` time window between consecutive steps.
    """
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
        # Try to find the sequence in order, respecting within_hours
        matched_alerts = []
        seq_idx = 0
        for a in group:
            if seq_idx >= len(sequence):
                break
            step = sequence[seq_idx]
            if _matches_title(a, step["title_pattern"]):
                # 检查时间窗口：当前步骤与上一步骤之间的时间差
                if matched_alerts and step.get("within_hours"):
                    prev_time = matched_alerts[-1].get("created_at") or matched_alerts[-1].get("timestamp")
                    curr_time = a.get("created_at") or a.get("timestamp")
                    if prev_time and curr_time:
                        try:
                            from datetime import datetime
                            t1 = datetime.fromisoformat(str(prev_time).replace("Z", "+00:00"))
                            t2 = datetime.fromisoformat(str(curr_time).replace("Z", "+00:00"))
                            diff_hours = abs((t2 - t1).total_seconds()) / 3600
                            if diff_hours > step["within_hours"]:
                                continue  # 超出时间窗口，跳过
                        except (ValueError, TypeError):
                            pass  # 时间解析失败时不做时间窗口限制
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
        "id": rule.get("id", ""),
        "name": rule.get("name", ""),
        "description": rule.get("description", ""),
        "risk_boost": rule.get("risk_boost", ""),
        "mitre_chain": rule.get("mitre_chain", []),
    }


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def match_rules(alerts: list[dict] | str) -> str:
    """对一组告警执行关联规则匹配

    Args:
        alerts: 告警数组；优先直接传结构化数组，也兼容 JSON 字符串

    Returns:
        JSON: {"matched_rules": [{"rule": {...}, "matched_alerts": [...], "evidence": "..."}]}
    """
    if isinstance(alerts, str):
        try:
            alerts = json.loads(alerts)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("match_rules: alerts JSON 解析失败: %s", exc)
            return json.dumps({"error": f"alerts JSON 解析失败: {exc}"}, ensure_ascii=False)

    if not isinstance(alerts, list):
        logger.warning("match_rules: alerts 参数类型错误: %s", type(alerts))
        return json.dumps({"error": "alerts 必须为数组"}, ensure_ascii=False)

    logger.info("match_rules: 开始匹配 %d 条告警, 共 %d 条规则", len(alerts), len(CORRELATION_RULES))

    matched = []
    for rule in CORRELATION_RULES:
        try:
            result = _check_rule(rule, alerts)
            if result:
                matched.append(result)
                logger.info("规则 [%s] 匹配成功", rule.get("name", rule.get("id")))
        except Exception as exc:
            logger.error("规则 %s 匹配异常: %s", rule.get("id", "?"), exc, exc_info=True)

    logger.info("match_rules: 共匹配 %d 条规则", len(matched))
    return json.dumps({"matched_rules": matched}, ensure_ascii=False)


@mcp.tool()
def get_rules() -> str:
    """查询当前所有关联规则

    Returns:
        JSON 格式的规则列表（不含内部匹配逻辑）
    """
    logger.info("get_rules: 返回 %d 条规则", len(CORRELATION_RULES))
    rules_info = []
    for r in CORRELATION_RULES:
        rules_info.append(
            {
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "risk_boost": r.get("risk_boost", ""),
                "mitre_chain": r.get("mitre_chain", []),
            }
        )
    return json.dumps({"rules": rules_info}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
