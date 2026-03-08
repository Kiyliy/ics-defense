import { Router } from 'express';

const router = Router();

/**
 * GET /api/approval
 * 查询审批列表，支持 ?status=pending 过滤
 */
router.get('/', (req, res) => {
  const { status } = req.query;
  const db = req.db;

  let where = [];
  let params = {};
  if (status) {
    where.push('status = @status');
    params.status = status;
  }

  const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';
  const approvals = db.prepare(
    `SELECT * FROM approval_queue ${whereClause} ORDER BY created_at DESC`
  ).all(params);
  const total = db.prepare(
    `SELECT COUNT(*) as count FROM approval_queue ${whereClause}`
  ).get(params);

  res.json({ approvals, total: total.count });
});

/**
 * GET /api/approval/:id
 * 查询单个审批详情
 */
router.get('/:id', (req, res) => {
  const db = req.db;
  const approval = db.prepare('SELECT * FROM approval_queue WHERE id = ?').get(req.params.id);

  if (!approval) {
    return res.status(404).json({ error: 'Approval not found' });
  }

  res.json(approval);
});

/**
 * PATCH /api/approval/:id
 * 审批操作：approved / rejected
 * Body: { status: "approved" | "rejected", reason: "可选原因" }
 */
router.patch('/:id', (req, res) => {
  const { status, reason } = req.body;
  const db = req.db;

  if (!['approved', 'rejected'].includes(status)) {
    return res.status(400).json({ error: 'status must be approved or rejected' });
  }

  // 检查当前状态是否为 pending
  const current = db.prepare('SELECT * FROM approval_queue WHERE id = ?').get(req.params.id);
  if (!current) {
    return res.status(404).json({ error: 'Approval not found' });
  }
  if (current.status !== 'pending') {
    return res.status(400).json({ error: 'Only pending approvals can be updated' });
  }

  const now = new Date().toISOString();
  db.prepare(
    'UPDATE approval_queue SET status = ?, reason = COALESCE(?, reason), responded_at = ? WHERE id = ?'
  ).run(status, reason || null, now, req.params.id);

  const updated = db.prepare('SELECT * FROM approval_queue WHERE id = ?').get(req.params.id);
  res.json(updated);
});

export default router;
