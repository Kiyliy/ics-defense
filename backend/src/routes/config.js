// @ts-check

import { Router } from 'express';
import {
  getConfig,
  setConfig,
  getAllConfig,
  batchSetConfig,
  reloadCache,
} from '../services/config.js';

const router = Router();

/**
 * GET /api/config
 * 返回全部系统配置
 */
router.get('/', (_req, res) => {
  const configs = getAllConfig();
  res.json({ configs });
});

/**
 * GET /api/config/:key
 * 查询单个配置项
 */
router.get('/:key', (req, res) => {
  const configs = getAllConfig();
  const item = configs.find((c) => c.key === req.params.key);
  if (!item) {
    return res.status(404).json({ error: `Config key "${req.params.key}" not found` });
  }
  res.json(item);
});

/**
 * PUT /api/config/:key
 * 更新单个配置项
 * Body: { value: "新值" }
 */
router.put('/:key', (req, res) => {
  const { value } = req.body;
  if (value === undefined || value === null) {
    return res.status(400).json({ error: 'value is required' });
  }

  const configs = getAllConfig();
  const exists = configs.find((c) => c.key === req.params.key);
  if (!exists) {
    return res.status(404).json({ error: `Config key "${req.params.key}" not found` });
  }

  setConfig(req.params.key, String(value));
  res.json({ key: req.params.key, value: String(value), updated: true });
});

/**
 * PUT /api/config
 * 批量更新配置
 * Body: { "rate_limit.global.max": "1000", "chat.max_messages": "100" }
 */
router.put('/', (req, res) => {
  const entries = req.body;
  if (!entries || typeof entries !== 'object' || Array.isArray(entries)) {
    return res.status(400).json({ error: 'Body must be a JSON object of { key: value } pairs' });
  }

  const { updated, unknown } = batchSetConfig(entries);
  res.json({ updated, unknown });
});

/**
 * POST /api/config/reload
 * 重新从数据库加载配置到内存缓存（用于外部直接修改数据库后同步）
 */
router.post('/reload', (_req, res) => {
  reloadCache();
  res.json({ reloaded: true });
});

export default router;
