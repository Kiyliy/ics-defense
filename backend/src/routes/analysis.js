// @ts-check

import { Router } from 'express';
import { analyzeAlerts, chat } from '../services/llm.js';
import { asyncHandler } from '../middleware/asyncHandler.js';
import { getConfigInt } from '../services/config.js';

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

/**
 * @typedef {{ trace_id: string, status?: string, message?: string }} AgentServiceResponse
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
    throw new Error(`Agent Service returned ${resp.status}`);
  }
  return /** @type {Promise<AgentServiceResponse>} */ (resp.json());
}

/**
 * 获取 Python Agent Service 状态
 * @param {{ fetchFn?: typeof fetch, agentServiceUrl?: string }} [options]
 * @returns {Promise<any>}
 */
async function getAgentServiceStatus({ fetchFn = fetch, agentServiceUrl = AGENT_SERVICE_URL } = {}) {
  const resp = await fetchFn(`${agentServiceUrl}/status`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new Error(`Agent Service returned ${resp.status}`);
  }
  return resp.json();
}

/**
 * POST /api/analysis/alerts
 * AI 分析告警：委托 Python Agent Service 进行分析
 *
 * Body: { alert_ids: [1, 2, 3] }
 */
export function createAnalysisRouter({
  fetchFn = fetch,
  chatFn = chat,
  agentServiceUrl = AGENT_SERVICE_URL,
} = {}) {
  const router = Router();

  router.get('/agent/status', asyncHandler(async (_req, res) => {
    try {
      const status = await getAgentServiceStatus({ fetchFn, agentServiceUrl });
      return res.json(status);
    } catch (agentErr) {
      console.error('Agent status unavailable:', getErrorMessage(agentErr));
      return res.status(503).json({ error: 'Agent Service unavailable' });
    }
  }));

  router.post('/alerts', asyncHandler(async (/** @type {any} */ req, /** @type {any} */ res) => {
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
      console.error('Agent Service unavailable:', getErrorMessage(agentErr));
      return res.status(503).json({ error: 'Agent Service unavailable' });
    }
  }));

/**
 * POST /api/analysis/chat
 * AI 对话：指挥面板中的自由问答
 *
 * Body: { messages: [{ role: 'user', content: '...' }] }
 */
  router.post('/chat', asyncHandler(async (/** @type {any} */ req, /** @type {any} */ res) => {
    const { messages } = req.body;
    if (!Array.isArray(messages)) {
      return res.status(400).json({ error: 'messages[] required' });
    }
    const maxMessages = getConfigInt('chat.max_messages', 50);
    if (messages.length > maxMessages) {
      return res.status(400).json({ error: `messages[] exceeds max length (${maxMessages})` });
    }
    try {
      const reply = await chatFn(messages);
      res.json({ reply });
    } catch (err) {
      console.error('Chat failed:', getErrorMessage(err));
      res.status(500).json({ error: 'Chat service temporarily unavailable' });
    }
  }));

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
      let alertIds = [];
      try { alertIds = JSON.parse(c.alert_ids || '[]'); } catch { /* ignore */ }
      const alerts = alertIds.length > 0 ? getAlerts.all(c.alert_ids) : [];

      const decisions = getDecisions.all(c.id);

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
 * Uses transaction for atomicity.
 */
  router.patch('/decisions/:id', (/** @type {any} */ req, /** @type {any} */ res) => {
    const { status } = req.body;
    if (!['accepted', 'rejected'].includes(status)) {
      return res.status(400).json({ error: 'status must be accepted or rejected' });
    }
    const db = req.db;

    // Atomic update: only succeeds if decision is still pending
    const result = db.prepare(
      'UPDATE decisions SET status = ? WHERE id = ? AND status = ?'
    ).run(status, req.params.id, 'pending');

    if (result.changes === 0) {
      const exists = db.prepare('SELECT id, status FROM decisions WHERE id = ?').get(req.params.id);
      if (!exists) {
        return res.status(404).json({ error: 'Decision not found' });
      }
      return res.status(400).json({ error: `Decision already processed (status: ${exists.status})` });
    }

    // Update related alert statuses in a transaction
    const updateRelatedAlerts = db.transaction(() => {
      const decision = db.prepare('SELECT attack_chain_id FROM decisions WHERE id = ?').get(req.params.id);
      if (decision) {
        const chain = db.prepare('SELECT alert_ids FROM attack_chains WHERE id = ?').get(decision.attack_chain_id);
        if (chain && chain.alert_ids) {
          try {
            const alertIds = JSON.parse(chain.alert_ids);
            const updateAlert = db.prepare('UPDATE alerts SET status = ? WHERE id = ?');
            const newAlertStatus = status === 'accepted' ? 'resolved' : 'analyzed';
            for (const alertId of alertIds) {
              updateAlert.run(newAlertStatus, alertId);
            }
          } catch { /* ignore malformed alert_ids */ }
        }
      }

      // Write audit log
      db.prepare(
        `INSERT INTO audit_logs (trace_id, alert_id, event_type, data) VALUES (?, ?, ?, ?)`
      ).run(
        `decision-${req.params.id}`,
        '',
        'decision_feedback',
        JSON.stringify({ decision_id: req.params.id, status })
      );
    });

    try {
      updateRelatedAlerts();
    } catch (err) {
      console.error('Failed to update related alerts:', err);
      // Decision itself was updated, but related alert updates failed
    }

    res.json({ updated: true });
  });

  return router;
}

export default createAnalysisRouter();
