// @ts-check

import { Router } from 'express';

const router = Router();

/**
 * @typedef {{ input_tokens?: number, prompt_tokens?: number, output_tokens?: number, completion_tokens?: number }} TokenUsage
 */

/** @typedef {{ [key: string]: string | number }} QueryParams */

/**
 * @param {string | null | undefined} raw
 * @returns {TokenUsage | null}
 */
function parseTokenUsage(raw) {
  if (!raw) return null;
  try {
    return /** @type {TokenUsage} */ (JSON.parse(raw));
  } catch {
    return null;
  }
}

/**
 * @param {unknown} rawDays
 * @returns {{ ok: true, days: number } | { ok: false, error: string }}
 */
function parseDays(rawDays) {
  if (rawDays === undefined || rawDays === null || rawDays === '') {
    return { ok: true, days: 7 };
  }

  const days = Number(rawDays);
  if (!Number.isFinite(days) || days < 0) {
    return { ok: false, error: 'days must be a non-negative number' };
  }

  return { ok: true, days };
}

/**
 * @param {number} days
 * @returns {string}
 */
function buildSinceIso(days) {
  const since = new Date();
  since.setDate(since.getDate() - days);
  return since.toISOString();
}

/**
 * GET /api/audit
 * 查询审计日志，支持 trace_id / alert_id / days 过滤和分页
 */
router.get('/', (/** @type {any} */ req, /** @type {any} */ res) => {
  const { trace_id, alert_id, days, limit = 50, offset = 0 } = req.query;
  const db = req.db;

  const parsedDays = parseDays(days);
  if (!parsedDays.ok) {
    return res.status(400).json({ error: parsedDays.error });
  }

  /** @type {string[]} */
  const where = [];
  /** @type {QueryParams} */
  const params = {};
  if (trace_id) { where.push('trace_id = @trace_id'); params.trace_id = String(trace_id); }
  if (alert_id) { where.push('alert_id = @alert_id'); params.alert_id = String(alert_id); }
  where.push('created_at >= @since');
  params.since = buildSinceIso(parsedDays.days);

  const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';
  params.limit = Number(limit);
  params.offset = Number(offset);

  const logs = db.prepare(
    `SELECT * FROM audit_logs ${whereClause} ORDER BY created_at ASC LIMIT @limit OFFSET @offset`
  ).all(params);
  const total = db.prepare(
    `SELECT COUNT(*) as count FROM audit_logs ${whereClause}`
  ).get(
    Object.fromEntries(Object.entries(params).filter(([key]) => !['limit', 'offset'].includes(key)))
  );

  res.json({ logs, total: total.count });
});

/**
 * GET /api/audit/stats
 * Token 用量统计，支持 ?days=7
 */
router.get('/stats', (/** @type {any} */ req, /** @type {any} */ res) => {
  const { days } = req.query;
  const db = req.db;
  const parsedDays = parseDays(days);
  if (!parsedDays.ok) {
    return res.status(400).json({ error: parsedDays.error });
  }

  const sinceStr = buildSinceIso(parsedDays.days);

  const totalAnalyses = db.prepare(
    `SELECT COUNT(DISTINCT trace_id) as count FROM audit_logs WHERE created_at >= ?`
  ).get(sinceStr);

  const tokenRows = db.prepare(
    `SELECT token_usage, DATE(created_at) as date FROM audit_logs WHERE token_usage IS NOT NULL AND created_at >= ?`
  ).all(sinceStr);

  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  /** @type {Record<string, { date: string, analyses: number, tokens: number }>} */
  const dailyMap = {};

  for (const row of tokenRows) {
    const usage = parseTokenUsage(row.token_usage);
    if (!usage) continue;

    const input = usage.input_tokens || usage.prompt_tokens || 0;
    const output = usage.output_tokens || usage.completion_tokens || 0;
    totalInputTokens += input;
    totalOutputTokens += output;

    if (!dailyMap[row.date]) {
      dailyMap[row.date] = { date: row.date, analyses: 0, tokens: 0 };
    }
    dailyMap[row.date].tokens += input + output;
  }

  const dailyAnalyses = db.prepare(
    `SELECT DATE(created_at) as date, COUNT(DISTINCT trace_id) as analyses
     FROM audit_logs WHERE created_at >= ?
     GROUP BY DATE(created_at)`
  ).all(sinceStr);

  for (const row of dailyAnalyses) {
    if (!dailyMap[row.date]) {
      dailyMap[row.date] = { date: row.date, analyses: 0, tokens: 0 };
    }
    dailyMap[row.date].analyses = row.analyses;
  }

  const daily = Object.values(dailyMap).sort((left, right) => left.date.localeCompare(right.date));

  res.json({
    total_analyses: totalAnalyses.count,
    total_input_tokens: totalInputTokens,
    total_output_tokens: totalOutputTokens,
    daily,
  });
});

/**
 * GET /api/audit/trace/:trace_id
 * 查询完整推理链
 */
router.get('/trace/:trace_id', (/** @type {any} */ req, /** @type {any} */ res) => {
  const db = req.db;
  const { trace_id } = req.params;

  const logs = db.prepare(
    'SELECT * FROM audit_logs WHERE trace_id = ? ORDER BY created_at ASC'
  ).all(trace_id);

  if (logs.length === 0) {
    return res.status(404).json({ error: 'Trace not found' });
  }

  let totalTokens = 0;
  for (const log of logs) {
    const usage = parseTokenUsage(log.token_usage);
    if (!usage) continue;

    totalTokens += (usage.input_tokens || usage.prompt_tokens || 0)
      + (usage.output_tokens || usage.completion_tokens || 0);
  }

  res.json({
    trace_id,
    logs,
    summary: {
      total_steps: logs.length,
      total_tokens: totalTokens,
    },
  });
});

export default router;
