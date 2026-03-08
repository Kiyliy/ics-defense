// @ts-check

/**
 * 多源事件规范化服务
 *
 * 将来自不同安全设备的原始日志统一为标准告警格式。
 * 支持的数据源：WAF（雷池）、NIDS（Suricata）、HIDS（Wazuh）、PIKACHU 靶场、SOC 日志
 */

const TACTIC_KEYWORDS = {
  scan: { tactic: 'Reconnaissance', technique: 'T0846' },
  brute: { tactic: 'Initial Access', technique: 'T0866' },
  login: { tactic: 'Initial Access', technique: 'T0078' },
  injection: { tactic: 'Execution', technique: 'T0807' },
  xss: { tactic: 'Execution', technique: 'T0807' },
  sql: { tactic: 'Execution', technique: 'T0807' },
  rce: { tactic: 'Execution', technique: 'T0807' },
  upload: { tactic: 'Persistence', technique: 'T0839' },
  shell: { tactic: 'Execution', technique: 'T0807' },
  privilege: { tactic: 'Privilege Escalation', technique: 'T0890' },
  exfiltration: { tactic: 'Exfiltration', technique: 'T0882' },
  c2: { tactic: 'Command and Control', technique: 'T0869' },
  dos: { tactic: 'Impact', technique: 'T0814' },
};

/**
 * @typedef {{
 *   source: string
 *   severity: string
 *   title: string
 *   description: string
 *   src_ip?: string
 *   dst_ip?: string
 *   tactic?: string
 *   technique?: string | null
 *   mitre_tactic?: string
 *   mitre_technique?: string | null
 *   raw_event_id?: number | bigint
 * }} NormalizedAlert
 */

/** @typedef {'waf' | 'nids' | 'hids' | 'pikachu'} NormalizerKey */

/**
 * @param {unknown} value
 * @returns {Record<string, any>}
 */
function asObject(value) {
  return value && typeof value === 'object' ? /** @type {Record<string, any>} */ (value) : {};
}

/**
 * 根据告警标题/描述推断 MITRE ATT&CK 映射
 * @param {string | undefined | null} text
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
 * @param {unknown} raw
 */
function normalizeSeverity(raw) {
  const severity = String(raw || '').toLowerCase();
  if (['critical', 'crit', '严重', '4', '5'].some((item) => severity.includes(item))) return 'critical';
  if (['high', '高', '3'].some((item) => severity.includes(item))) return 'high';
  if (['medium', 'med', '中', '2'].some((item) => severity.includes(item))) return 'medium';
  return 'low';
}

/** @param {unknown} raw */
function normalizeWAF(raw) {
  const event = asObject(raw);
  return {
    source: 'waf',
    severity: normalizeSeverity(event.severity || event.risk_level),
    title: event.rule_name || event.event_type || 'WAF Alert',
    description: event.reason || event.detail || JSON.stringify(event),
    src_ip: event.src_ip || event.remote_addr,
    dst_ip: event.dst_ip || event.server_addr,
    ...inferMitre(event.rule_name || event.event_type),
  };
}

/** @param {unknown} raw */
function normalizeNIDS(raw) {
  const event = asObject(raw);
  const alert = asObject(event.alert);
  return {
    source: 'nids',
    severity: normalizeSeverity(alert.severity),
    title: alert.signature || 'NIDS Alert',
    description: `SID:${alert.signature_id} Category:${alert.category || 'N/A'}`,
    src_ip: event.src_ip,
    dst_ip: event.dest_ip || event.dst_ip,
    ...inferMitre(alert.signature || alert.category),
  };
}

/** @param {unknown} raw */
function normalizeHIDS(raw) {
  const event = asObject(raw);
  const rule = asObject(event.rule);
  const data = asObject(event.data);
  const agent = asObject(event.agent);
  return {
    source: 'hids',
    severity: normalizeSeverity(rule.level),
    title: rule.description || 'HIDS Alert',
    description: `Rule:${rule.id} Groups:${(Array.isArray(rule.groups) ? rule.groups : []).join(',')}`,
    src_ip: data.srcip || agent.ip,
    dst_ip: agent.ip,
    ...inferMitre(rule.description),
  };
}

/** @param {unknown} raw */
function normalizePikachu(raw) {
  const event = asObject(raw);
  return {
    source: 'pikachu',
    severity: normalizeSeverity(event.severity || 'medium'),
    title: event.vuln_type || event.title || 'Pikachu Alert',
    description: event.payload || event.detail || JSON.stringify(event),
    src_ip: event.src_ip || event.attacker_ip,
    dst_ip: event.dst_ip || event.target_ip,
    ...inferMitre(event.vuln_type || event.title),
  };
}

/** @param {unknown} raw */
function normalizeGeneric(raw) {
  const event = asObject(raw);
  return {
    source: event.source || 'soc',
    severity: normalizeSeverity(event.severity),
    title: event.title || event.message || 'Generic Alert',
    description: event.description || JSON.stringify(event),
    src_ip: event.src_ip,
    dst_ip: event.dst_ip,
    ...inferMitre(event.title || event.message),
  };
}

/**
 * 主入口：根据来源类型分发到对应的规范化函数
 * @param {string} source
 * @param {unknown} rawEvent
 * @returns {NormalizedAlert}
 */
export function normalize(source, rawEvent) {
  /** @type {Record<NormalizerKey, (raw: unknown) => NormalizedAlert>} */
  const normalizers = {
    waf: normalizeWAF,
    nids: normalizeNIDS,
    hids: normalizeHIDS,
    pikachu: normalizePikachu,
  };

  const handler = source in normalizers
    ? normalizers[/** @type {NormalizerKey} */ (source)]
    : normalizeGeneric;

  const normalized = /** @type {NormalizedAlert} */ (handler(rawEvent));
  normalized.mitre_tactic = normalized.tactic;
  normalized.mitre_technique = normalized.technique;
  delete normalized.tactic;
  delete normalized.technique;
  return normalized;
}
