import { Router } from 'express';
import { analyzeAlerts, chat } from '../services/llm.js';

const router = Router();

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

/**
 * 调用 Python Agent Service 进行分析
 * 返回 trace_id 供前端轮询进度
 */
async function callAgentService(alertIds) {
  const resp = await fetch(`${AGENT_SERVICE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alert_ids: alertIds }),
  });
  if (!resp.ok) {
    throw new Error(`Agent Service returned ${resp.status}: ${await resp.text()}`);
  }
  return resp.json();
}

/**
 * 直接调用 LLM 分析（fallback）
 */
async function analyzeWithLLM(db, alerts, alertIds) {
  const result = await analyzeAlerts(alerts);

  // 存攻击链
  const chainInsert = db.prepare(`
    INSERT INTO attack_chains (name, stage, confidence, alert_ids, evidence)
    VALUES (@name, @stage, @confidence, @alert_ids, @evidence)
  `);
  const chainResult = chainInsert.run({
    name: result.mitre_tactic || 'Unknown Chain',
    stage: result.mitre_tactic || 'unknown',
    confidence: result.confidence || 0,
    alert_ids: JSON.stringify(alertIds),
    evidence: result.rationale || result.analysis || '',
  });

  // 存处置建议
  const decisionInsert = db.prepare(`
    INSERT INTO decisions (attack_chain_id, risk_level, recommendation, action_type, rationale)
    VALUES (@attack_chain_id, @risk_level, @recommendation, @action_type, @rationale)
  `);
  decisionInsert.run({
    attack_chain_id: chainResult.lastInsertRowid,
    risk_level: result.risk_level || 'medium',
    recommendation: result.recommendation || '',
    action_type: result.action_type || 'investigate',
    rationale: result.rationale || '',
  });

  // 更新告警状态为 analyzing
  const updateStatus = db.prepare('UPDATE alerts SET status = ? WHERE id = ?');
  for (const id of alertIds) {
    updateStatus.run('analyzing', id);
  }

  return {
    attack_chain_id: Number(chainResult.lastInsertRowid),
    analysis: result,
  };
}

/**
 * POST /api/analysis/alerts
 * AI 分析告警：优先调用 Python Agent Service，失败时 fallback 到直接 LLM 调用
 *
 * Body: { alert_ids: [1, 2, 3] }
 */
router.post('/alerts', async (req, res) => {
  const { alert_ids } = req.body;
  if (!Array.isArray(alert_ids) || alert_ids.length === 0) {
    return res.status(400).json({ error: 'alert_ids[] required' });
  }

  const db = req.db;
  const placeholders = alert_ids.map(() => '?').join(',');
  const alerts = db.prepare(`SELECT * FROM alerts WHERE id IN (${placeholders})`).all(...alert_ids);

  if (alerts.length === 0) {
    return res.status(404).json({ error: 'No alerts found' });
  }

  // 优先调用 Agent Service
  try {
    const agentResult = await callAgentService(alert_ids);

    // 更新告警状态为 analyzing
    const updateStatus = db.prepare('UPDATE alerts SET status = ? WHERE id = ?');
    for (const id of alert_ids) {
      updateStatus.run('analyzing', id);
    }

    return res.json({
      trace_id: agentResult.trace_id,
      status: 'analyzing',
      message: 'Analysis delegated to Agent Service',
    });
  } catch (agentErr) {
    console.warn('Agent Service unavailable, falling back to direct LLM:', agentErr.message);
  }

  // Fallback: 直接调用 LLM
  try {
    const result = await analyzeWithLLM(db, alerts, alert_ids);
    res.json(result);
  } catch (err) {
    console.error('LLM analysis failed:', err.message);
    res.status(500).json({ error: 'AI analysis failed', detail: err.message });
  }
});

/**
 * POST /api/analysis/chat
 * AI 对话：指挥面板中的自由问答
 *
 * Body: { messages: [{ role: 'user', content: '...' }] }
 */
router.post('/chat', async (req, res) => {
  const { messages } = req.body;
  if (!Array.isArray(messages)) {
    return res.status(400).json({ error: 'messages[] required' });
  }
  try {
    const reply = await chat(messages);
    res.json({ reply });
  } catch (err) {
    console.error('Chat failed:', err.message);
    res.status(500).json({ error: 'Chat failed', detail: err.message });
  }
});

/**
 * GET /api/analysis/chains
 * 查询攻击链列表
 */
router.get('/chains', (req, res) => {
  const chains = req.db.prepare(`
    SELECT c.*, d.risk_level, d.recommendation, d.action_type
    FROM attack_chains c
    LEFT JOIN decisions d ON d.attack_chain_id = c.id
    ORDER BY c.created_at DESC
    LIMIT 50
  `).all();
  res.json({ chains });
});

/**
 * PATCH /api/analysis/decisions/:id
 * 人工反馈：接受或拒绝处置建议
 */
router.patch('/decisions/:id', (req, res) => {
  const { status } = req.body;
  if (!['accepted', 'rejected'].includes(status)) {
    return res.status(400).json({ error: 'status must be accepted or rejected' });
  }
  const result = req.db.prepare('UPDATE decisions SET status = ? WHERE id = ?').run(status, req.params.id);
  res.json({ updated: result.changes > 0 });
});

export default router;
