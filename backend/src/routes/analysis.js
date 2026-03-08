// @ts-check

import { Router } from 'express';
import { analyzeAlerts, chat } from '../services/llm.js';

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

/**
 * @typedef {{ trace_id: string, status?: string, message?: string }} AgentServiceResponse
 */

/**
 * @typedef {{
 *   analysis?: string
 *   mitre_tactic?: string
 *   mitre_technique?: string
 *   risk_level?: string
 *   confidence?: number
 *   recommendation?: string
 *   action_type?: string
 *   rationale?: string
 * }} LLMAnalysisResult
 */

/**
 * @param {unknown} error
 * @returns {string}
 */
function getErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

/**
 * @param {number[]} requestedIds
 * @param {{ id: number }[]} alerts
 * @returns {number[]}
 */
function findMissingAlertIds(requestedIds, alerts) {
  const foundIds = new Set(alerts.map((alert) => Number(alert.id)));
  return requestedIds.filter((id) => !foundIds.has(id));
}

/**
 * 调用 Python Agent Service 进行分析
 * 返回 trace_id 供前端轮询进度
 * @param {number[]} alertIds
 * @param {{ fetchFn?: typeof fetch, agentServiceUrl?: string }} [options]
 * @returns {Promise<AgentServiceResponse>}
 */
async function callAgentService(alertIds, { fetchFn = fetch, agentServiceUrl = AGENT_SERVICE_URL } = {}) {
  const resp = await fetchFn(`${agentServiceUrl}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alert_ids: alertIds }),
  });
  if (!resp.ok) {
    throw new Error(`Agent Service returned ${resp.status}: ${await resp.text()}`);
  }
  return /** @type {Promise<AgentServiceResponse>} */ (resp.json());
}

/**
 * 直接调用 LLM 分析（fallback）
 * @param {any} db
 * @param {unknown[]} alerts
 * @param {number[]} alertIds
 * @param {{ analyzeAlertsFn?: typeof analyzeAlerts }} [options]
 */
async function analyzeWithLLM(db, alerts, alertIds, { analyzeAlertsFn = analyzeAlerts } = {}) {
  const result = /** @type {LLMAnalysisResult} */ (await analyzeAlertsFn(alerts));

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

  // fallback 为同步分析，完成后直接进入完成态
  const updateStatus = db.prepare('UPDATE alerts SET status = ? WHERE id = ?');
  for (const id of alertIds) {
    updateStatus.run('resolved', id);
  }

  return {
    attack_chain_id: Number(chainResult.lastInsertRowid),
    analysis: result,
  };
}

/**
 * POST /api/analysis/alerts
 * AI 分析告警：委托 Python Agent Service 进行分析，不可用时返回 503
 *
 * Body: { alert_ids: [1, 2, 3] }
 */
export function createAnalysisRouter({
  fetchFn = fetch,
  analyzeAlertsFn = analyzeAlerts,
  chatFn = chat,
  agentServiceUrl = AGENT_SERVICE_URL,
} = {}) {
  const router = Router();

  router.post('/alerts', async (/** @type {any} */ req, /** @type {any} */ res) => {
    const { alert_ids } = req.body;
    if (!Array.isArray(alert_ids) || alert_ids.length === 0) {
      return res.status(400).json({ error: 'alert_ids[] required' });
    }

    if (!alert_ids.every((id) => Number.isInteger(id) && id > 0)) {
      return res.status(400).json({ error: 'alert_ids must contain positive integers' });
    }

    const db = req.db;
    const placeholders = alert_ids.map(() => '?').join(',');
    const alerts = db.prepare(`SELECT * FROM alerts WHERE id IN (${placeholders})`).all(...alert_ids);

    if (alerts.length === 0) {
      return res.status(404).json({ error: 'No alerts found' });
    }

    const missingIds = findMissingAlertIds(alert_ids, alerts);
    if (missingIds.length > 0) {
      return res.status(404).json({ error: 'Some alerts were not found', missing_alert_ids: missingIds });
    }

    try {
      const agentResult = await callAgentService(alert_ids, { fetchFn, agentServiceUrl });
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
      const message = getErrorMessage(agentErr);
      console.error('Agent Service unavailable:', message);
      res.status(503).json({ error: 'Agent Service unavailable', detail: message });
    }
  });

/**
 * POST /api/analysis/chat
 * AI 对话：指挥面板中的自由问答
 *
 * Body: { messages: [{ role: 'user', content: '...' }] }
 */
  router.post('/chat', async (/** @type {any} */ req, /** @type {any} */ res) => {
    const { messages } = req.body;
    if (!Array.isArray(messages)) {
      return res.status(400).json({ error: 'messages[] required' });
    }
    try {
      const reply = await chatFn(messages);
      res.json({ reply });
    } catch (err) {
      const message = getErrorMessage(err);
      console.error('Chat failed:', message);
      res.status(500).json({ error: 'Chat failed', detail: message });
    }
  });

/**
 * GET /api/analysis/chains
 * 查询攻击链列表
 */
  router.get('/chains', (/** @type {any} */ req, /** @type {any} */ res) => {
    const db = req.db;
    const rawChains = db.prepare(`
      SELECT c.*
      FROM attack_chains c
      ORDER BY c.created_at DESC
      LIMIT 50
    `).all();

    const getAlerts = db.prepare(`SELECT id, title, severity, src_ip FROM alerts WHERE id IN (SELECT value FROM json_each(?))`);
    const getDecisions = db.prepare(`SELECT * FROM decisions WHERE attack_chain_id = ? ORDER BY created_at DESC, id DESC`);

    const chains = rawChains.map((/** @type {any} */ c) => {
      // Parse alert_ids and fetch related alerts
      let alertIds = [];
      try { alertIds = JSON.parse(c.alert_ids || '[]'); } catch { /* ignore */ }
      const alerts = alertIds.length > 0 ? getAlerts.all(c.alert_ids) : [];

      // Fetch decisions for this chain
      const decisions = getDecisions.all(c.id);

      // Derive alert_count and status
      const alert_count = alertIds.length;
      const pendingDecisions = decisions.filter((/** @type {any} */ d) => d.status === 'pending');
      const status = decisions.length === 0 ? 'new' : pendingDecisions.length > 0 ? 'pending' : 'resolved';

      const primaryDecision = decisions[0] || null;
      const risk_level = primaryDecision?.risk_level || c.risk_level || 'medium';
      const recommendation = primaryDecision?.recommendation || null;
      const action_type = primaryDecision?.action_type || null;
      const decision_status = primaryDecision?.status || null;

      return {
        ...c,
        alerts,
        decisions: decisions.map((decision) => ({
          ...decision,
          action: decision.recommendation,
        })),
        alert_count,
        status,
        risk_level,
        recommendation,
        action_type,
        decision_status,
      };
    });

    res.json({ chains });
  });

/**
 * PATCH /api/analysis/decisions/:id
 * 人工反馈：接受或拒绝处置建议
 */
  router.patch('/decisions/:id', (/** @type {any} */ req, /** @type {any} */ res) => {
    const { status } = req.body;
    if (!['accepted', 'rejected'].includes(status)) {
      return res.status(400).json({ error: 'status must be accepted or rejected' });
    }
    const db = req.db;
    const result = db.prepare('UPDATE decisions SET status = ? WHERE id = ?').run(status, req.params.id);
    if (result.changes === 0) {
      return res.status(404).json({ error: 'Decision not found' });
    }

    // When a decision is accepted, resolve all related alerts
    if (status === 'accepted') {
      const decision = db.prepare('SELECT attack_chain_id FROM decisions WHERE id = ?').get(req.params.id);
      if (decision) {
        const chain = db.prepare('SELECT alert_ids FROM attack_chains WHERE id = ?').get(decision.attack_chain_id);
        if (chain && chain.alert_ids) {
          try {
            const alertIds = JSON.parse(chain.alert_ids);
            const updateAlert = db.prepare('UPDATE alerts SET status = ? WHERE id = ?');
            for (const alertId of alertIds) {
              updateAlert.run('resolved', alertId);
            }
          } catch { /* ignore malformed alert_ids */ }
        }
      }
    }

    res.json({ updated: true });
  });

  return router;
}

export default createAnalysisRouter();
