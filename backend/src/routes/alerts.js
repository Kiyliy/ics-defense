// @ts-check

import { Router } from 'express';
import { normalize } from '../services/normalizer.js';
import { getConfig, getConfigInt } from '../services/config.js';

const router = Router();

/** @typedef {{ [key: string]: string | number }} QueryParams */

/**
 * @param {unknown} rawValue
 * @param {string} fieldName
 * @returns {{ ok: true, value: number } | { ok: false, error: string }}
 */
function parseNonNegativeInteger(rawValue, fieldName) {
  const value = Number(rawValue);
  if (!Number.isInteger(value) || value < 0) {
    return { ok: false, error: `${fieldName} must be a non-negative integer` };
  }
  return { ok: true, value };
}

/**
 * POST /api/alerts/ingest
 * 多源事件接入：接收原始日志，规范化后存入数据库
 *
 * Body: { source: 'waf'|'nids'|'hids'|'pikachu'|'soc', events: [...] }
 */
router.post('/ingest', (/** @type {any} */ req, /** @type {any} */ res) => {
  const { source, events } = req.body;
  if (!source || !Array.isArray(events)) {
    return res.status(400).json({ error: 'source and events[] required' });
  }

  // 从 system_config 动态读取
  const validSources = getConfig('ingest.valid_sources', 'waf,nids,hids,pikachu,soc').split(',').map((s) => s.trim());
  const maxBatchSize = getConfigInt('ingest.max_batch_size', 1000);

  if (!validSources.includes(source)) {
    return res.status(400).json({ error: `source must be one of: ${validSources.join(', ')}` });
  }
  if (events.length === 0) {
    return res.status(400).json({ error: 'events[] must not be empty' });
  }
  if (events.length > maxBatchSize) {
    return res.status(400).json({ error: `events[] exceeds max batch size (${maxBatchSize})` });
  }

  const db = req.db;
  const insertRaw = db.prepare(
    'INSERT INTO raw_events (source, raw_json) VALUES (?, ?)'
  );
  const findSimilar = db.prepare(`
    SELECT id FROM alerts
    WHERE source = @source AND title = @title AND severity = @severity
      AND created_at >= datetime('now', '-' || @window_hours || ' hours')
    ORDER BY created_at DESC LIMIT 1
  `);
  const incrementCount = db.prepare(
    'UPDATE alerts SET event_count = event_count + 1 WHERE id = ?'
  );
  const insertAlert = db.prepare(`
    INSERT INTO alerts (source, severity, title, description, src_ip, dst_ip, mitre_tactic, mitre_technique, raw_event_id, event_count)
    VALUES (@source, @severity, @title, @description, @src_ip, @dst_ip, @mitre_tactic, @mitre_technique, @raw_event_id, 1)
  `);

  const clusteringWindow = getConfigInt('ingest.clustering_window_hours', 1);

  /** @type {Record<string, unknown>[]} */
  const results = [];
  const batchInsert = db.transaction(() => {
    for (const event of events) {
      const rawResult = insertRaw.run(source, JSON.stringify(event));
      const normalized = normalize(source, event);
      normalized.raw_event_id = rawResult.lastInsertRowid;

      // 聚簇：同 source + title + severity 在窗口内的归并
      const existing = findSimilar.get({ ...normalized, window_hours: clusteringWindow });
      if (existing) {
        incrementCount.run(existing.id);
        results.push({ id: existing.id, clustered: true, ...normalized });
      } else {
        const alertResult = insertAlert.run(normalized);
        results.push({ id: Number(alertResult.lastInsertRowid), ...normalized });
      }
    }
  });

  try {
    batchInsert();
  } catch (err) {
    console.error('Ingest batch failed:', err);
    return res.status(500).json({ error: 'Failed to ingest events' });
  }
  res.json({ ingested: results.length, alerts: results });
});

/**
 * GET /api/alerts
 * 查询告警列表，支持筛选和分页
 */
router.get('/', (/** @type {any} */ req, /** @type {any} */ res) => {
  const { status, severity, source, limit = 50, offset = 0 } = req.query;
  const db = req.db;

  const parsedLimit = parseNonNegativeInteger(limit, 'limit');
  if (!parsedLimit.ok) return res.status(400).json({ error: parsedLimit.error });
  const parsedOffset = parseNonNegativeInteger(offset, 'offset');
  if (!parsedOffset.ok) return res.status(400).json({ error: parsedOffset.error });

  /** @type {string[]} */
  const where = [];
  /** @type {QueryParams} */
  const params = {};
  if (status) { where.push('status = @status'); params.status = String(status); }
  if (severity) { where.push('severity = @severity'); params.severity = String(severity); }
  if (source) { where.push('source = @source'); params.source = String(source); }

  const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';
  const sql = `SELECT * FROM alerts ${whereClause} ORDER BY created_at DESC LIMIT @limit OFFSET @offset`;
  params.limit = parsedLimit.value;
  params.offset = parsedOffset.value;

  const alerts = db.prepare(sql).all(params);
  const countParams = Object.fromEntries(
    Object.entries(params).filter(([key]) => !['limit', 'offset'].includes(key))
  );
  const total = db.prepare(`SELECT COUNT(*) as count FROM alerts ${whereClause}`).get(countParams);

  res.json({ total: total.count, alerts });
});

/**
 * GET /api/alerts/:id
 * 查询单条告警详情
 */
router.get('/:id', (/** @type {any} */ req, /** @type {any} */ res) => {
  const alert = req.db.prepare(
    'SELECT a.*, r.raw_json, r.source as raw_source FROM alerts a LEFT JOIN raw_events r ON a.raw_event_id = r.id WHERE a.id = ?'
  ).get(req.params.id);
  if (!alert) {
    return res.status(404).json({ error: 'Alert not found' });
  }
  if (alert.raw_json) {
    try {
      alert.raw_json = JSON.parse(alert.raw_json);
    } catch { /* keep as string if not valid JSON */ }
  }
  res.json(alert);
});

/**
 * Valid alert state transitions: open → analyzing → analyzed → resolved
 * @type {Record<string, string[]>}
 */
const VALID_TRANSITIONS = {
  open: ['analyzing'],
  analyzing: ['analyzed', 'open'],     // allow rollback to open on failure
  analyzed: ['resolved', 'open'],      // allow reopen
  resolved: ['open'],                  // allow reopen
};

/**
 * PATCH /api/alerts/:id/status
 * 更新告警状态（人工反馈闭环），校验状态转换合法性
 */
router.patch('/:id/status', (/** @type {any} */ req, /** @type {any} */ res) => {
  const { status } = req.body;
  if (!['open', 'analyzing', 'analyzed', 'resolved'].includes(status)) {
    return res.status(400).json({ error: 'Invalid status' });
  }

  const db = req.db;
  const current = db.prepare('SELECT id, status FROM alerts WHERE id = ?').get(req.params.id);
  if (!current) {
    return res.status(404).json({ error: 'Alert not found' });
  }

  const allowed = VALID_TRANSITIONS[current.status] || [];
  if (!allowed.includes(status)) {
    return res.status(400).json({
      error: `Invalid transition: ${current.status} → ${status}. Allowed: ${allowed.join(', ') || 'none'}`,
    });
  }

  db.prepare('UPDATE alerts SET status = ? WHERE id = ?').run(status, req.params.id);

  // Write audit log for status change
  db.prepare(
    `INSERT INTO audit_logs (trace_id, alert_id, event_type, data) VALUES (?, ?, ?, ?)`
  ).run(
    `manual-${Date.now()}`,
    String(req.params.id),
    'alert_status_change',
    JSON.stringify({ from: current.status, to: status })
  );

  res.json({ updated: true });
});

export default router;
