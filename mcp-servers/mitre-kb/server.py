import json
import logging
import re
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("mitre-kb")

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
    {
        "id": "T0817", "name": "Drive-by Compromise", "name_zh": "水坑攻击",
        "tactic": "TA0100", "description": "通过受害者正常浏览的网站投放恶意代码",
        "platforms": ["Control Server", "Human-Machine Interface"],
        "data_sources": ["Network Traffic", "Process Monitoring"],
        "mitigations": ["Application Isolation and Sandboxing", "Restrict Web-Based Content"],
    },
    {
        "id": "T0866", "name": "Exploitation of Remote Services", "name_zh": "远程服务利用",
        "tactic": "TA0100", "description": "利用远程服务漏洞获取初始访问",
        "platforms": ["Control Server", "Engineering Workstation"],
        "data_sources": ["Network Traffic", "Application Log"],
        "mitigations": ["Network Segmentation", "Vulnerability Scanning", "Update Software"],
    },
    {
        "id": "T0078", "name": "Valid Accounts", "name_zh": "合法账户",
        "tactic": "TA0100", "description": "使用合法凭证进行访问，包括暴力破解获取的凭证",
        "platforms": ["Control Server", "Engineering Workstation", "Human-Machine Interface"],
        "data_sources": ["Authentication Logs", "Process Monitoring"],
        "mitigations": ["Multi-factor Authentication", "Account Use Policies", "Password Policies"],
    },
    {
        "id": "T0807", "name": "Command-Line Interface", "name_zh": "命令行接口",
        "tactic": "TA0104", "description": "通过命令行执行恶意命令",
        "platforms": ["Control Server", "Engineering Workstation"],
        "data_sources": ["Process Monitoring", "Process Command-line Parameters"],
        "mitigations": ["Execution Prevention", "Disable or Remove Feature or Program"],
    },
    {
        "id": "T0871", "name": "Execution through API", "name_zh": "API执行",
        "tactic": "TA0104", "description": "通过工控系统API执行命令，包括OPC-UA/DA接口调用",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED"],
        "data_sources": ["Application Log", "Network Traffic"],
        "mitigations": ["Authorization Enforcement", "Network Segmentation"],
    },
    {
        "id": "T0890", "name": "Exploitation for Privilege Escalation", "name_zh": "漏洞利用提权",
        "tactic": "TA0104", "description": "利用软件漏洞（如SQL注入）进行权限提升",
        "platforms": ["Control Server", "Engineering Workstation"],
        "data_sources": ["Application Log", "Process Monitoring"],
        "mitigations": ["Update Software", "Application Isolation and Sandboxing"],
    },
    {
        "id": "T0839", "name": "Module Firmware", "name_zh": "固件篡改",
        "tactic": "TA0098", "description": "修改设备固件实现持久化，可影响PLC/RTU正常运行",
        "platforms": ["Field Controller/RTU/PLC/IED", "Safety Instrumented System/Protection Relay"],
        "data_sources": ["Firmware Modification", "Asset Inventory"],
        "mitigations": ["Boot Integrity", "Code Signing", "Network Segmentation"],
    },
    {
        "id": "T0846", "name": "Remote System Discovery", "name_zh": "远程系统发现",
        "tactic": "TA0106", "description": "扫描发现网络中的其他系统，包括端口扫描和协议识别",
        "platforms": ["Control Server", "Engineering Workstation"],
        "data_sources": ["Network Traffic", "Packet Capture"],
        "mitigations": ["Network Segmentation", "Network Intrusion Prevention"],
    },
    {
        "id": "T0812", "name": "Default Credentials", "name_zh": "默认凭证",
        "tactic": "TA0109", "description": "使用设备默认凭证进行横向移动，工控设备常保留出厂默认密码",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED", "Human-Machine Interface"],
        "data_sources": ["Authentication Logs", "Network Traffic"],
        "mitigations": ["Password Policies", "Account Use Policies"],
    },
    {
        "id": "T0882", "name": "Theft of Operational Information", "name_zh": "运营信息窃取",
        "tactic": "TA0110", "description": "窃取工控系统运行数据和配置信息，如过程变量、设备配置",
        "platforms": ["Control Server", "Human-Machine Interface"],
        "data_sources": ["Network Traffic", "Application Log"],
        "mitigations": ["Network Segmentation", "Encrypt Sensitive Information"],
    },
    {
        "id": "T0855", "name": "Unauthorized Command Message", "name_zh": "未授权指令",
        "tactic": "TA0108",
        "description": "攻击者发送未授权的命令消息来指示控制系统资产执行超出其预期功能的操作，或在不具备逻辑前提条件的情况下发出命令",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED", "Safety Instrumented System/Protection Relay"],
        "data_sources": ["Network Traffic", "Packet Capture", "Sequential Event Recorder"],
        "mitigations": ["Communication Authenticity", "Network Allowlists", "Authorization Enforcement"],
    },
    {
        "id": "T0831", "name": "Manipulation of Control", "name_zh": "控制操纵",
        "tactic": "TA0108", "description": "操纵工业控制系统的控制逻辑，篡改设定值或控制参数",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED", "Human-Machine Interface"],
        "data_sources": ["Network Traffic", "Sequential Event Recorder"],
        "mitigations": ["Communication Authenticity", "Network Segmentation", "Authorization Enforcement"],
    },
    {
        "id": "T0879", "name": "Damage to Property", "name_zh": "财产损坏",
        "tactic": "TA0040", "description": "导致物理设备或设施损坏，可能造成安全事故",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED", "Safety Instrumented System/Protection Relay"],
        "data_sources": ["Asset Inventory", "Sequential Event Recorder"],
        "mitigations": ["Safety Instrumented Systems", "Mechanical Protection Layers"],
    },
    {
        "id": "T0813", "name": "Denial of Control", "name_zh": "控制拒绝",
        "tactic": "TA0040", "description": "阻止操作员控制工控系统，可能导致无法响应异常工况",
        "platforms": ["Control Server", "Human-Machine Interface"],
        "data_sources": ["Network Traffic", "Application Log"],
        "mitigations": ["Redundancy of Service", "Network Segmentation"],
    },
    {
        "id": "T0826", "name": "Loss of Availability", "name_zh": "可用性丧失",
        "tactic": "TA0040", "description": "导致工控系统不可用，影响工业过程持续运行",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED"],
        "data_sources": ["Network Traffic", "Sequential Event Recorder"],
        "mitigations": ["Redundancy of Service", "Data Backup"],
    },
    {
        "id": "T0803", "name": "Block Command Message", "name_zh": "阻断命令消息",
        "tactic": "TA0107",
        "description": "攻击者阻断命令消息以阻止对紧急情况或过程故障的自动或操作员响应，可导致控制拒绝。适用于串行和以太网工控通信协议",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED"],
        "data_sources": ["Network Traffic", "Packet Capture"],
        "mitigations": ["Network Segmentation", "Communication Authenticity", "Network Allowlists"],
    },
    {
        "id": "T0814", "name": "Denial of Service", "name_zh": "拒绝服务",
        "tactic": "TA0107",
        "description": "通过资源耗尽或协议滥用使工控系统服务不可用",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED", "Human-Machine Interface"],
        "data_sources": ["Network Traffic", "Application Log"],
        "mitigations": ["Network Segmentation", "Filter Network Traffic"],
    },
    {
        "id": "T0869", "name": "Standard Application Layer Protocol", "name_zh": "标准应用层协议",
        "tactic": "TA0111",
        "description": "利用标准应用层协议（HTTP/HTTPS/DNS等）进行命令与控制通信",
        "platforms": ["Control Server", "Engineering Workstation"],
        "data_sources": ["Network Traffic", "Packet Capture"],
        "mitigations": ["Network Intrusion Prevention", "Filter Network Traffic"],
    },
    {
        "id": "T0886", "name": "Remote Services", "name_zh": "远程服务",
        "tactic": "TA0109",
        "description": "使用合法远程服务（如VNC/RDP/SSH）进行横向移动",
        "platforms": ["Control Server", "Engineering Workstation", "Human-Machine Interface"],
        "data_sources": ["Authentication Logs", "Network Traffic"],
        "mitigations": ["Multi-factor Authentication", "Network Segmentation", "Account Use Policies"],
    },
    {
        "id": "T0836", "name": "Modify Parameter", "name_zh": "修改参数",
        "tactic": "TA0108",
        "description": "修改工控系统运行参数（如阈值、设定值），可能导致过程异常",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED", "Human-Machine Interface"],
        "data_sources": ["Application Log", "Sequential Event Recorder"],
        "mitigations": ["Authorization Enforcement", "Communication Authenticity"],
    },
    {
        "id": "T0856", "name": "Spoof Reporting Message", "name_zh": "伪造报告消息",
        "tactic": "TA0105",
        "description": "伪造发送到控制系统的报告消息，使操作员获得错误的系统状态信息",
        "platforms": ["Control Server", "Field Controller/RTU/PLC/IED"],
        "data_sources": ["Network Traffic", "Packet Capture"],
        "mitigations": ["Communication Authenticity", "Network Segmentation"],
    },
    {
        "id": "T0861", "name": "Point & Tag Identification", "name_zh": "点位与标签识别",
        "tactic": "TA0110",
        "description": "识别工控系统中的数据点和标签，用于后续的数据收集或控制操纵",
        "platforms": ["Control Server", "Human-Machine Interface"],
        "data_sources": ["Network Traffic", "Application Log"],
        "mitigations": ["Network Segmentation", "Restrict Library Loading"],
    },
]

# 关键词到技术的映射（用于 map_alert_to_mitre）
KEYWORD_TECHNIQUE_MAP = {
    "sql注入|sql injection|sqli|union select|sqlmap": "T0890",
    "端口扫描|port scan|nmap|masscan|网络探测|网络扫描": "T0846",
    "暴力破解|brute force|login fail|认证失败|密码爆破": "T0078",
    "命令注入|command injection|rce|远程执行|远程代码": "T0807",
    "横向移动|lateral movement|内网渗透|psexec|wmi远程": "T0812",
    "数据外泄|exfiltration|数据窃取|敏感数据传输": "T0882",
    "固件|firmware|固件篡改|固件上传": "T0839",
    "未授权|unauthorized|非法指令|未授权指令": "T0855",
    "阻断命令|block command|命令阻断|阻断消息": "T0803",
    "拒绝服务|dos|denial|flood|资源耗尽": "T0826",
    "水坑|drive-by|钓鱼|watering hole": "T0817",
    "api调用|api exploit|opc-ua|opcua|opc ua": "T0871",
    "控制操纵|manipulation|篡改控制|修改设定值": "T0831",
    "modbus异常|modbus.*非法|modbus.*exception|功能码异常": "T0855",
    "dnp3.*异常|dnp3.*非法|dnp3.*unauthorized": "T0855",
    "远程服务|remote service|vnc|rdp|ssh.*异常": "T0886",
    "参数修改|modify parameter|设定值.*变更|阈值.*修改": "T0836",
    "伪造.*报告|spoof.*report|虚假.*状态": "T0856",
    "点位.*识别|tag.*identification|标签.*扫描": "T0861",
    "拒绝.*控制|denial.*control|控制.*丧失": "T0813",
    "可用性.*丧失|loss.*availability|系统.*不可用": "T0826",
    "财产.*损坏|damage.*property|设备.*损坏|物理.*破坏": "T0879",
}


@mcp.tool()
def lookup_technique(technique_id: str) -> str:
    """查询 ATT&CK for ICS 技术详情

    Args:
        technique_id: 技术ID，如 "T0890"

    Returns:
        JSON: 技术详情（id, name, name_zh, tactic, description, platforms, data_sources, mitigations）
        如果未找到返回 {"error": "未找到技术 <id>"}
    """
    if not technique_id or not technique_id.strip():
        logger.warning("lookup_technique: technique_id 为空")
        return json.dumps({"error": "technique_id 不能为空"}, ensure_ascii=False)

    technique_id = technique_id.strip().upper()
    logger.info("lookup_technique: %s", technique_id)

    for t in ICS_TECHNIQUES:
        if t["id"] == technique_id:
            logger.info("找到技术: %s - %s", t["id"], t["name"])
            return json.dumps(t, ensure_ascii=False)

    logger.info("未找到技术: %s", technique_id)
    return json.dumps({"error": f"未找到技术 {technique_id}"}, ensure_ascii=False)


@mcp.tool()
def lookup_tactic(tactic_id: str) -> str:
    """查询 ATT&CK for ICS 战术阶段

    Args:
        tactic_id: 战术ID，如 "TA0100"

    Returns:
        JSON: 战术详情 + 该战术下的所有技术列表
    """
    if not tactic_id or not tactic_id.strip():
        logger.warning("lookup_tactic: tactic_id 为空")
        return json.dumps({"error": "tactic_id 不能为空"}, ensure_ascii=False)

    tactic_id = tactic_id.strip().upper()
    logger.info("lookup_tactic: %s", tactic_id)

    for tac in ICS_TACTICS:
        if tac["id"] == tactic_id:
            techniques = [t for t in ICS_TECHNIQUES if t["tactic"] == tactic_id]
            result = {**tac, "techniques": techniques}
            logger.info("找到战术: %s - %s，包含 %d 个技术", tac["id"], tac["name"], len(techniques))
            return json.dumps(result, ensure_ascii=False)

    logger.info("未找到战术: %s", tactic_id)
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
    if not alert_title or not alert_title.strip():
        logger.warning("map_alert_to_mitre: alert_title 为空")
        return json.dumps({"matched_techniques": [], "note": "alert_title 为空"}, ensure_ascii=False)

    text = (alert_title + " " + alert_description).strip()
    logger.info("map_alert_to_mitre: 匹配文本='%s'", text[:200])

    matched = []
    seen_ids = set()

    for pattern, tech_id in KEYWORD_TECHNIQUE_MAP.items():
        try:
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
        except re.error as exc:
            logger.warning("正则匹配错误 pattern='%s': %s", pattern, exc)

    # confidence based on total matches
    total = len(matched)
    for m in matched:
        m["confidence"] = round(min(0.6 + 0.2 * total, 1.0), 2)

    logger.info("map_alert_to_mitre: 匹配到 %d 个技术", total)
    return json.dumps({"matched_techniques": matched}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
