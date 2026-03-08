import json
import re
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="mitre-kb", instructions="MITRE ATT&CK for ICS 知识库查询")

# 内嵌 ICS ATT&CK 数据（不需要外部文件）
ICS_TACTICS = [
    {"id": "TA0100", "name": "Initial Access", "name_zh": "初始访问", "description": "攻击者获取工控网络初始立足点的技术"},
    {"id": "TA0104", "name": "Execution", "name_zh": "执行", "description": "在工控系统上运行恶意代码的技术"},
    {"id": "TA0098", "name": "Persistence", "name_zh": "持久化", "description": "攻击者维持对工控系统访问的技术"},
    {"id": "TA0105", "name": "Evasion", "name_zh": "防御规避", "description": "避免被检测的技术"},
    {"id": "TA0106", "name": "Discovery", "name_zh": "发现", "description": "发现工控网络和设备信息的技术"},
    {"id": "TA0109", "name": "Lateral Movement", "name_zh": "横向移动", "description": "在工控网络中横向移动的技术"},
    {"id": "TA0110", "name": "Collection", "name_zh": "收集", "description": "收集工控系统数据的技术"},
    {"id": "TA0111", "name": "Command and Control", "name_zh": "命令与控制", "description": "与受控工控系统通信的技术"},
    {"id": "TA0107", "name": "Inhibit Response Function", "name_zh": "抑制响应功能", "description": "阻止安全系统响应的技术"},
    {"id": "TA0108", "name": "Impair Process Control", "name_zh": "破坏过程控制", "description": "操纵工业过程控制的技术"},
    {"id": "TA0040", "name": "Impact", "name_zh": "影响", "description": "造成破坏性影响的技术"},
]

ICS_TECHNIQUES = [
    {"id": "T0817", "name": "Drive-by Compromise", "name_zh": "水坑攻击", "tactic": "TA0100", "description": "通过受害者正常浏览的网站投放恶意代码"},
    {"id": "T0866", "name": "Exploitation of Remote Services", "name_zh": "远程服务利用", "tactic": "TA0100", "description": "利用远程服务漏洞获取初始访问"},
    {"id": "T0078", "name": "Valid Accounts", "name_zh": "合法账户", "tactic": "TA0100", "description": "使用合法凭证进行访问，包括暴力破解获取的凭证"},
    {"id": "T0807", "name": "Command-Line Interface", "name_zh": "命令行接口", "tactic": "TA0104", "description": "通过命令行执行恶意命令"},
    {"id": "T0871", "name": "Execution through API", "name_zh": "API执行", "tactic": "TA0104", "description": "通过工控系统API执行命令"},
    {"id": "T0890", "name": "Exploitation for Privilege Escalation", "name_zh": "漏洞利用提权", "tactic": "TA0104", "description": "利用软件漏洞（如SQL注入）进行权限提升"},
    {"id": "T0839", "name": "Module Firmware", "name_zh": "固件篡改", "tactic": "TA0098", "description": "修改设备固件实现持久化"},
    {"id": "T0846", "name": "Remote System Discovery", "name_zh": "远程系统发现", "tactic": "TA0106", "description": "扫描发现网络中的其他系统，包括端口扫描"},
    {"id": "T0812", "name": "Default Credentials", "name_zh": "默认凭证", "tactic": "TA0109", "description": "使用设备默认凭证进行横向移动"},
    {"id": "T0882", "name": "Theft of Operational Information", "name_zh": "运营信息窃取", "tactic": "TA0110", "description": "窃取工控系统运行数据和配置信息"},
    {"id": "T0855", "name": "Unauthorized Command Message", "name_zh": "未授权指令", "tactic": "TA0108", "description": "向工控设备发送未授权的控制指令"},
    {"id": "T0831", "name": "Manipulation of Control", "name_zh": "控制操纵", "tactic": "TA0108", "description": "操纵工业控制系统的控制逻辑"},
    {"id": "T0879", "name": "Damage to Property", "name_zh": "财产损坏", "tactic": "TA0040", "description": "导致物理设备或设施损坏"},
    {"id": "T0813", "name": "Denial of Control", "name_zh": "控制拒绝", "tactic": "TA0040", "description": "阻止操作员控制工控系统"},
    {"id": "T0826", "name": "Loss of Availability", "name_zh": "可用性丧失", "tactic": "TA0040", "description": "导致工控系统不可用"},
]

# 关键词到技术的映射（用于 map_alert_to_mitre）
KEYWORD_TECHNIQUE_MAP = {
    "sql注入|sql injection|sqli": "T0890",
    "端口扫描|port scan|nmap|masscan": "T0846",
    "暴力破解|brute force|login fail|认证失败": "T0078",
    "命令注入|command injection|rce|远程执行": "T0807",
    "横向移动|lateral movement|内网渗透": "T0812",
    "数据外泄|exfiltration|数据窃取": "T0882",
    "固件|firmware": "T0839",
    "未授权|unauthorized|非法指令": "T0855",
    "拒绝服务|dos|denial": "T0826",
    "水坑|drive-by|钓鱼": "T0817",
    "api调用|api exploit": "T0871",
    "控制操纵|manipulation|篡改控制": "T0831",
}


@mcp.tool()
def lookup_technique(technique_id: str) -> str:
    """查询 ATT&CK for ICS 技术详情

    Args:
        technique_id: 技术ID，如 "T0890"

    Returns:
        JSON: 技术详情（id, name, name_zh, tactic, description）
        如果未找到返回 {"error": "未找到技术 <id>"}
    """
    technique_id = technique_id.strip().upper()
    for t in ICS_TECHNIQUES:
        if t["id"] == technique_id:
            return json.dumps(t, ensure_ascii=False)
    return json.dumps({"error": f"未找到技术 {technique_id}"}, ensure_ascii=False)


@mcp.tool()
def lookup_tactic(tactic_id: str) -> str:
    """查询 ATT&CK for ICS 战术阶段

    Args:
        tactic_id: 战术ID，如 "TA0100"

    Returns:
        JSON: 战术详情 + 该战术下的所有技术列表
    """
    tactic_id = tactic_id.strip().upper()
    for tac in ICS_TACTICS:
        if tac["id"] == tactic_id:
            techniques = [t for t in ICS_TECHNIQUES if t["tactic"] == tactic_id]
            result = {**tac, "techniques": techniques}
            return json.dumps(result, ensure_ascii=False)
    return json.dumps({"error": f"未找到战术 {tactic_id}"}, ensure_ascii=False)


@mcp.tool()
def map_alert_to_mitre(alert_title: str, alert_description: str = "") -> str:
    """将告警特征映射到 ATT&CK for ICS 技术

    Args:
        alert_title: 告警标题
        alert_description: 告警描述（可选）

    Returns:
        JSON: {"matched_techniques": [{"technique": {...}, "confidence": ..., "matched_keyword": "..."}]}
    """
    text = (alert_title + " " + alert_description).strip()
    matched = []
    seen_ids = set()

    for pattern, tech_id in KEYWORD_TECHNIQUE_MAP.items():
        if re.search(pattern, text, re.IGNORECASE):
            if tech_id not in seen_ids:
                seen_ids.add(tech_id)
                technique = None
                for t in ICS_TECHNIQUES:
                    if t["id"] == tech_id:
                        technique = t
                        break
                if technique:
                    matched.append({
                        "technique": technique,
                        "matched_keyword": pattern,
                    })

    # confidence based on total matches
    total = len(matched)
    for m in matched:
        m["confidence"] = round(min(0.6 + 0.2 * total, 1.0), 2)

    return json.dumps({"matched_techniques": matched}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
