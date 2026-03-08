// @ts-check

import { Router } from 'express';
import { normalize } from '../services/normalizer.js';

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

  const db = req.db;
  const insertRaw = db.prepare(
    'INSERT INTO raw_events (source, raw_json) VALUES (?, ?)'
  );
  const insertAlert = db.prepare(`
    INSERT INTO alerts (source, severity, title, description, src_ip, dst_ip, mitre_tactic, mitre_technique, raw_event_id)
    VALUES (@source, @severity, @title, @description, @src_ip, @dst_ip, @mitre_tactic, @mitre_technique, @raw_event_id)
  `);

  /** @type {Record<string, unknown>[]} */
  const results = [];
  const batchInsert = db.transaction(() => {
    for (const event of events) {
      const rawResult = insertRaw.run(source, JSON.stringify(event));
      const normalized = normalize(source, event);
      normalized.raw_event_id = rawResult.lastInsertRowid;
      const alertResult = insertAlert.run(normalized);
      results.push({ id: Number(alertResult.lastInsertRowid), ...normalized });
    }
  });

  batchInsert();
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
  const alert = req.db.prepare('SELECT * FROM alerts WHERE id = ?').get(req.params.id);
  if (!alert) {
    return res.status(404).json({ error: 'Alert not found' });
  }
  res.json(alert);
});

/**
 * PATCH /api/alerts/:id/status
 * 更新告警状态（人工反馈闭环）
 */
router.patch('/:id/status', (/** @type {any} */ req, /** @type {any} */ res) => {
  const { status } = req.body;
  if (!['open', 'analyzing', 'resolved'].includes(status)) {
    return res.status(400).json({ error: 'Invalid status' });
  }
  const result = req.db.prepare('UPDATE alerts SET status = ? WHERE id = ?').run(status, req.params.id);
  if (result.changes === 0) {
    return res.status(404).json({ error: 'Alert not found' });
  }
  res.json({ updated: true });
});

export default router;
