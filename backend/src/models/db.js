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
 * @param {string} dbPath
 * @returns {any}
 */
export function initDB(dbPath) {
  mkdirSync(dirname(dbPath), { recursive: true });
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  db.exec(SCHEMA);
  return db;
}
