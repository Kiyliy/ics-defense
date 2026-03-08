import { Router } from 'express';
import { normalize } from '../services/normalizer.js';

const router = Router();

/**
 * POST /api/alerts/ingest
 * 多源事件接入：接收原始日志，规范化后存入数据库
 *
 * Body: { source: 'waf'|'nids'|'hids'|'pikachu'|'soc', events: [...] }
 */
router.post('/ingest', (req, res) => {
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

  const results = [];
  const batchInsert = db.transaction(() => {
    for (const event of events) {
      // 1. 存原始事件
      const rawResult = insertRaw.run(source, JSON.stringify(event));
      // 2. 规范化
      const normalized = normalize(source, event);
      normalized.raw_event_id = rawResult.lastInsertRowid;
      // 3. 存告警
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
router.get('/', (req, res) => {
  const { status, severity, source, limit = 50, offset = 0 } = req.query;
  const db = req.db;

  let where = [];
  let params = {};
  if (status) { where.push('status = @status'); params.status = status; }
  if (severity) { where.push('severity = @severity'); params.severity = severity; }
  if (source) { where.push('source = @source'); params.source = source; }

  const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';
  const sql = `SELECT * FROM alerts ${whereClause} ORDER BY created_at DESC LIMIT @limit OFFSET @offset`;
  params.limit = Number(limit);
  params.offset = Number(offset);

  const alerts = db.prepare(sql).all(params);
  const total = db.prepare(`SELECT COUNT(*) as count FROM alerts ${whereClause}`).get(
    Object.fromEntries(Object.entries(params).filter(([k]) => !['limit', 'offset'].includes(k)))
  );

  res.json({ total: total.count, alerts });
});

/**
 * GET /api/alerts/:id
 * 查询单条告警详情
 */
router.get('/:id', (req, res) => {
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
router.patch('/:id/status', (req, res) => {
  const { status } = req.body;
  if (!['open', 'analyzing', 'resolved'].includes(status)) {
    return res.status(400).json({ error: 'Invalid status' });
  }
  const result = req.db.prepare('UPDATE alerts SET status = ? WHERE id = ?').run(status, req.params.id);
  res.json({ updated: result.changes > 0 });
});

export default router;
