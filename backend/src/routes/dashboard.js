import { Router } from 'express';

const router = Router();

/**
 * GET /api/dashboard/stats
 * 指挥面板统计数据
 */
router.get('/stats', (req, res) => {
  const db = req.db;

  const alertsByStatus = db.prepare(`
    SELECT status, COUNT(*) as count FROM alerts GROUP BY status
  `).all();

  const alertsBySeverity = db.prepare(`
    SELECT severity, COUNT(*) as count FROM alerts GROUP BY severity
  `).all();

  const alertsBySource = db.prepare(`
    SELECT source, COUNT(*) as count FROM alerts GROUP BY source
  `).all();

  const recentAlerts = db.prepare(`
    SELECT * FROM alerts ORDER BY created_at DESC LIMIT 10
  `).all();

  const activeChains = db.prepare(`
    SELECT c.*, d.risk_level, d.recommendation, d.action_type, d.status as decision_status
    FROM attack_chains c
    LEFT JOIN decisions d ON d.attack_chain_id = c.id
    ORDER BY c.created_at DESC LIMIT 5
  `).all();

  const totalAlerts = db.prepare('SELECT COUNT(*) as count FROM alerts').get();
  const totalChains = db.prepare('SELECT COUNT(*) as count FROM attack_chains').get();
  const pendingDecisions = db.prepare(
    "SELECT COUNT(*) as count FROM decisions WHERE status = 'pending'"
  ).get();

  res.json({
    summary: {
      totalAlerts: totalAlerts.count,
      totalChains: totalChains.count,
      pendingDecisions: pendingDecisions.count,
    },
    alertsByStatus,
    alertsBySeverity,
    alertsBySource,
    recentAlerts,
    activeChains,
  });
});

/**
 * GET /api/dashboard/trend
 * 最近7天告警趋势
 */
router.get('/trend', (req, res) => {
  const trend = req.db.prepare(`
    SELECT date(created_at) as date, COUNT(*) as count
    FROM alerts
    WHERE created_at >= date('now', '-7 days')
    GROUP BY date(created_at)
    ORDER BY date ASC
  `).all();
  res.json({ trend });
});

/**
 * GET /api/dashboard/assets
 * 资产列表
 */
router.get('/assets', (req, res) => {
  const assets = req.db.prepare(`
    SELECT a.*,
      (SELECT COUNT(*) FROM alerts WHERE dst_ip = a.ip) as alert_count
    FROM assets a
    ORDER BY alert_count DESC
  `).all();
  res.json({ assets });
});

/**
 * POST /api/dashboard/assets
 * 添加资产
 */
router.post('/assets', (req, res) => {
  const { ip, hostname, type, importance } = req.body;
  if (!ip) return res.status(400).json({ error: 'ip required' });

  const result = req.db.prepare(
    'INSERT INTO assets (ip, hostname, type, importance) VALUES (?, ?, ?, ?)'
  ).run(ip, hostname || null, type || 'host', importance || 3);

  res.json({ id: Number(result.lastInsertRowid) });
});

export default router;
