import { Router } from 'express';

const router = Router();

/**
 * GET /api/audit
 * 查询审计日志，支持 trace_id / alert_id 过滤和分页
 */
router.get('/', (req, res) => {
  const { trace_id, alert_id, limit = 50, offset = 0 } = req.query;
  const db = req.db;

  let where = [];
  let params = {};
  if (trace_id) { where.push('trace_id = @trace_id'); params.trace_id = trace_id; }
  if (alert_id) { where.push('alert_id = @alert_id'); params.alert_id = alert_id; }

  const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';
  params.limit = Number(limit);
  params.offset = Number(offset);

  const logs = db.prepare(
    `SELECT * FROM audit_logs ${whereClause} ORDER BY created_at ASC LIMIT @limit OFFSET @offset`
  ).all(params);
  const total = db.prepare(
    `SELECT COUNT(*) as count FROM audit_logs ${whereClause}`
  ).get(
    Object.fromEntries(Object.entries(params).filter(([k]) => !['limit', 'offset'].includes(k)))
  );

  res.json({ logs, total: total.count });
});

/**
 * GET /api/audit/stats
 * Token 用量统计，支持 ?days=7
 */
router.get('/stats', (req, res) => {
  const { days = 7 } = req.query;
  const db = req.db;
  const daysNum = Number(days);

  const since = new Date();
  since.setDate(since.getDate() - daysNum);
  const sinceStr = since.toISOString();

  // 总分析次数（不同 trace_id 数量）
  const totalAnalyses = db.prepare(
    `SELECT COUNT(DISTINCT trace_id) as count FROM audit_logs WHERE created_at >= ?`
  ).get(sinceStr);

  // 获取所有有 token_usage 的记录
  const tokenRows = db.prepare(
    `SELECT token_usage, DATE(created_at) as date FROM audit_logs WHERE token_usage IS NOT NULL AND created_at >= ?`
  ).all(sinceStr);

  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  const dailyMap = {};

  for (const row of tokenRows) {
    try {
      const usage = JSON.parse(row.token_usage);
      const input = usage.input_tokens || usage.prompt_tokens || 0;
      const output = usage.output_tokens || usage.completion_tokens || 0;
      totalInputTokens += input;
      totalOutputTokens += output;

      if (!dailyMap[row.date]) {
        dailyMap[row.date] = { date: row.date, analyses: 0, tokens: 0 };
      }
      dailyMap[row.date].tokens += input + output;
    } catch {
      // 跳过无法解析的记录
    }
  }

  // 统计每日分析次数
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

  const daily = Object.values(dailyMap).sort((a, b) => a.date.localeCompare(b.date));

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
router.get('/trace/:trace_id', (req, res) => {
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
    if (log.token_usage) {
      try {
        const usage = JSON.parse(log.token_usage);
        totalTokens += (usage.input_tokens || usage.prompt_tokens || 0)
                     + (usage.output_tokens || usage.completion_tokens || 0);
      } catch {
        // 跳过无法解析的记录
      }
    }
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
