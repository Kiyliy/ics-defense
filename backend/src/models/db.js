// @ts-check

import Database from 'better-sqlite3';
import { mkdirSync } from 'fs';
import { dirname } from 'path';

/**
 * 数据模型说明（对应开题报告 ER 图）：
 *
 * assets        - 资产（主机/设备），含 IP、类型、重要度
 * raw_events    - 原始事件（多源接入的原始日志，来自 WAF/NIDS/HIDS/靶场等）
 * alerts        - 告警（经规范化 + 聚合后的告警记录）
 * attack_chains - 攻击链（LLM 推断的攻击阶段与链路）
 * decisions     - 处置建议（AI 生成的策略建议）
 */

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS assets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ip          TEXT NOT NULL,
    hostname    TEXT,
    type        TEXT DEFAULT 'host',       -- host / network_device / server
    importance  INTEGER DEFAULT 3,         -- 1-5, 5 最重要
    created_at  TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS raw_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,             -- waf / nids / hids / pikachu / soc
    raw_json    TEXT NOT NULL,             -- 原始 JSON
    received_at TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS alerts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    severity      TEXT DEFAULT 'medium',   -- low / medium / high / critical
    title         TEXT NOT NULL,
    description   TEXT,
    src_ip        TEXT,
    dst_ip        TEXT,
    mitre_tactic  TEXT,                    -- MITRE ATT&CK 战术
    mitre_technique TEXT,                  -- MITRE ATT&CK 技术 ID
    asset_id      INTEGER REFERENCES assets(id),
    status        TEXT DEFAULT 'open',     -- lifecycle: open → analyzing → analyzed → resolved
    raw_event_id  INTEGER REFERENCES raw_events(id),
    event_count   INTEGER DEFAULT 1,            -- 聚簇：关联的原始日志条数
    created_at    TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS attack_chains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT,
    stage       TEXT,                      -- reconnaissance / initial_access / execution / ...
    confidence  REAL DEFAULT 0.0,          -- 0-1 置信度
    alert_ids   TEXT,                      -- JSON 数组, 关联的告警 ID
    evidence    TEXT,                      -- LLM 推理证据
    created_at  TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attack_chain_id INTEGER REFERENCES attack_chains(id),
    risk_level      TEXT DEFAULT 'medium', -- low / medium / high / critical
    recommendation  TEXT NOT NULL,         -- AI 生成的处置建议
    action_type     TEXT,                  -- block / isolate / monitor / investigate
    rationale       TEXT,                  -- 推理依据
    status          TEXT DEFAULT 'pending', -- pending / accepted / rejected
    created_at      TEXT DEFAULT (datetime('now'))
  );

  CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
  CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
  CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);

  CREATE TABLE IF NOT EXISTS approval_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id      TEXT NOT NULL,
    tool_name     TEXT NOT NULL,
    tool_args     TEXT,
    reason        TEXT,
    status        TEXT DEFAULT 'pending',
    responded_at  DATETIME,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS audit_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id      TEXT NOT NULL,
    alert_id      TEXT,
    event_type    TEXT NOT NULL,
    data          TEXT,
    token_usage   TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE INDEX IF NOT EXISTS idx_alerts_asset ON alerts(asset_id);
  CREATE INDEX IF NOT EXISTS idx_alerts_raw_event ON alerts(raw_event_id);
  CREATE INDEX IF NOT EXISTS idx_decisions_chain ON decisions(attack_chain_id);
  CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_queue(status);
  CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_logs(trace_id);
  CREATE INDEX IF NOT EXISTS idx_audit_alert ON audit_logs(alert_id);

  -- 系统配置表：存储可动态调整的业务参数
  CREATE TABLE IF NOT EXISTS system_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
  );
`;

/**
 * 默认业务配置（仅在首次初始化时写入，不覆盖已有值）
 * @type {Array<{ key: string, value: string, description: string }>}
 */
const DEFAULT_CONFIG = [
  // LLM 配置
  { key: 'llm.model',        value: 'grok-3-mini-fast',       description: 'LLM 模型名称' },
  { key: 'llm.base_url',     value: 'https://api.x.ai/v1',   description: 'OpenAI 兼容 API 地址' },
  { key: 'llm.api_key',      value: '',                       description: 'API Key（敏感信息）' },
  { key: 'llm.temperature',  value: '0.5',  description: 'Chat 默认 temperature（0-1）' },
  { key: 'llm.max_tokens',   value: '4000', description: '最大输出 token 数' },
  // 系统配置
  { key: 'system.escalation_threshold', value: 'high',  description: '告警自动升级阈值（low/medium/high/critical）' },
  { key: 'system.auto_approval',        value: 'false', description: '是否自动审批低于阈值的处置建议' },
  // 速率限制 — 全局
  { key: 'rate_limit.global.window_ms',   value: '900000',  description: '全局速率限制窗口（毫秒），默认 15 分钟' },
  { key: 'rate_limit.global.max',         value: '500',     description: '全局速率限制窗口内最大请求数' },
  // 速率限制 — LLM
  { key: 'rate_limit.llm.window_ms',      value: '60000',   description: 'LLM 端点速率限制窗口（毫秒），默认 1 分钟' },
  { key: 'rate_limit.llm.max',            value: '10',      description: 'LLM 端点窗口内最大请求数' },
  // 速率限制 — 通知
  { key: 'rate_limit.notify.window_ms',   value: '60000',   description: '通知端点速率限制窗口（毫秒），默认 1 分钟' },
  { key: 'rate_limit.notify.max',         value: '20',      description: '通知端点窗口内最大请求数' },
  // 事件接入
  { key: 'ingest.max_batch_size',         value: '1000',    description: '单次 ingest 最大事件数' },
  { key: 'ingest.valid_sources',          value: 'waf,nids,hids,pikachu,soc', description: '允许的事件来源（逗号分隔）' },
  { key: 'ingest.clustering_window_hours', value: '1',      description: '告警聚类时间窗口（小时），相同告警在窗口内合并计数' },
  // Agent 服务
  { key: 'agent.service_url',   value: 'http://localhost:8002', description: 'Agent 服务地址' },
  // 通知
  { key: 'notification.provider',       value: 'feishu',  description: '通知渠道（feishu / feishu-app / noop）' },
  { key: 'notification.max_retries',    value: '5',       description: '通知发送最大重试次数' },
  { key: 'notification.base_delay_ms',  value: '1000',    description: '通知重试基础延迟（毫秒）' },
  { key: 'notification.max_delay_ms',   value: '30000',   description: '通知重试最大延迟（毫秒）' },
  // 对话
  { key: 'chat.max_messages',             value: '50',      description: 'chat 接口单次最大消息数' },
  // 请求体
  { key: 'request.body_limit',            value: '1mb',     description: '请求体大小上限' },
];

/**
 * @param {string} dbPath
 * @returns {any}
 */
export function initDB(dbPath) {
  mkdirSync(dirname(dbPath), { recursive: true });
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  db.exec(SCHEMA);

  // Migration: add event_count column to existing databases
  try {
    db.prepare('SELECT event_count FROM alerts LIMIT 1').get();
  } catch {
    db.exec('ALTER TABLE alerts ADD COLUMN event_count INTEGER DEFAULT 1');
  }

  // Seed default config (INSERT OR IGNORE — never overwrite existing values)
  const upsert = db.prepare(
    'INSERT OR IGNORE INTO system_config (key, value, description) VALUES (?, ?, ?)'
  );
  const seedAll = db.transaction(() => {
    for (const row of DEFAULT_CONFIG) {
      upsert.run(row.key, row.value, row.description);
    }
  });
  seedAll();

  return db;
}
