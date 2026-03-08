/**
 * 多源事件规范化服务
 *
 * 将来自不同安全设备的原始日志统一为标准告警格式。
 * 支持的数据源：WAF（雷池）、NIDS（Suricata）、HIDS（Wazuh）、PIKACHU 靶场、SOC 日志
 */

// MITRE ATT&CK for ICS 战术映射（简化版）
const TACTIC_KEYWORDS = {
  'scan': { tactic: 'Reconnaissance', technique: 'T0846' },
  'brute': { tactic: 'Initial Access', technique: 'T0866' },
  'login': { tactic: 'Initial Access', technique: 'T0078' },
  'injection': { tactic: 'Execution', technique: 'T0807' },
  'xss': { tactic: 'Execution', technique: 'T0807' },
  'sql': { tactic: 'Execution', technique: 'T0807' },
  'rce': { tactic: 'Execution', technique: 'T0807' },
  'upload': { tactic: 'Persistence', technique: 'T0839' },
  'shell': { tactic: 'Execution', technique: 'T0807' },
  'privilege': { tactic: 'Privilege Escalation', technique: 'T0890' },
  'exfiltration': { tactic: 'Exfiltration', technique: 'T0882' },
  'c2': { tactic: 'Command and Control', technique: 'T0869' },
  'dos': { tactic: 'Impact', technique: 'T0814' },
};

/**
 * 根据告警标题/描述推断 MITRE ATT&CK 映射
 */
function inferMitre(text) {
  const lower = (text || '').toLowerCase();
  for (const [keyword, mapping] of Object.entries(TACTIC_KEYWORDS)) {
    if (lower.includes(keyword)) return mapping;
  }
  return { tactic: 'Unknown', technique: null };
}

/**
 * 严重度标准化
 */
function normalizeSeverity(raw) {
  const s = String(raw || '').toLowerCase();
  if (['critical', 'crit', '严重', '4', '5'].some(k => s.includes(k))) return 'critical';
  if (['high', '高', '3'].some(k => s.includes(k))) return 'high';
  if (['medium', 'med', '中', '2'].some(k => s.includes(k))) return 'medium';
  return 'low';
}

/**
 * WAF（雷池 SafeLine）日志规范化
 */
function normalizeWAF(raw) {
  return {
    source: 'waf',
    severity: normalizeSeverity(raw.severity || raw.risk_level),
    title: raw.rule_name || raw.event_type || 'WAF Alert',
    description: raw.reason || raw.detail || JSON.stringify(raw),
    src_ip: raw.src_ip || raw.remote_addr,
    dst_ip: raw.dst_ip || raw.server_addr,
    ...inferMitre(raw.rule_name || raw.event_type),
  };
}

/**
 * NIDS（Suricata）日志规范化
 */
function normalizeNIDS(raw) {
  const alert = raw.alert || {};
  return {
    source: 'nids',
    severity: normalizeSeverity(alert.severity),
    title: alert.signature || 'NIDS Alert',
    description: `SID:${alert.signature_id} Category:${alert.category || 'N/A'}`,
    src_ip: raw.src_ip,
    dst_ip: raw.dest_ip || raw.dst_ip,
    ...inferMitre(alert.signature || alert.category),
  };
}

/**
 * HIDS（Wazuh）日志规范化
 */
function normalizeHIDS(raw) {
  const rule = raw.rule || {};
  return {
    source: 'hids',
    severity: normalizeSeverity(rule.level),
    title: rule.description || 'HIDS Alert',
    description: `Rule:${rule.id} Groups:${(rule.groups || []).join(',')}`,
    src_ip: raw.data?.srcip || raw.agent?.ip,
    dst_ip: raw.agent?.ip,
    ...inferMitre(rule.description),
  };
}

/**
 * PIKACHU 靶场日志规范化
 */
function normalizePikachu(raw) {
  return {
    source: 'pikachu',
    severity: normalizeSeverity(raw.severity || 'medium'),
    title: raw.vuln_type || raw.title || 'Pikachu Alert',
    description: raw.payload || raw.detail || JSON.stringify(raw),
    src_ip: raw.src_ip || raw.attacker_ip,
    dst_ip: raw.dst_ip || raw.target_ip,
    ...inferMitre(raw.vuln_type || raw.title),
  };
}

/**
 * 通用 / SOC 日志规范化
 */
function normalizeGeneric(raw) {
  return {
    source: raw.source || 'soc',
    severity: normalizeSeverity(raw.severity),
    title: raw.title || raw.message || 'Generic Alert',
    description: raw.description || JSON.stringify(raw),
    src_ip: raw.src_ip,
    dst_ip: raw.dst_ip,
    ...inferMitre(raw.title || raw.message),
  };
}

/**
 * 主入口：根据来源类型分发到对应的规范化函数
 */
export function normalize(source, rawEvent) {
  const normalizers = {
    waf: normalizeWAF,
    nids: normalizeNIDS,
    hids: normalizeHIDS,
    pikachu: normalizePikachu,
  };
  const fn = normalizers[source] || normalizeGeneric;
  const normalized = fn(rawEvent);
  normalized.mitre_tactic = normalized.tactic;
  normalized.mitre_technique = normalized.technique;
  delete normalized.tactic;
  delete normalized.technique;
  return normalized;
}
