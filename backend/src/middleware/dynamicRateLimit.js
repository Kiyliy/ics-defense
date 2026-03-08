// @ts-check

import rateLimit from 'express-rate-limit';
import { getConfigInt } from '../services/config.js';

/**
 * 创建动态速率限制中间件 — 每隔一段时间从 system_config 重新读取参数。
 *
 * express-rate-limit 的 windowMs/max 在创建后不可变，所以这里用一个
 * wrapper：定期重建 limiter 实例来实现"热更新"。
 *
 * @param {{ windowMsKey: string, maxKey: string, defaultWindowMs: number, defaultMax: number, message: string }} opts
 * @returns {import('express').RequestHandler}
 */
export function createDynamicRateLimiter({ windowMsKey, maxKey, defaultWindowMs, defaultMax, message }) {
  let currentWindowMs = defaultWindowMs;
  let currentMax = defaultMax;
  /** @type {import('express').RequestHandler | null} */
  let limiter = buildLimiter(currentWindowMs, currentMax, message);

  // Check for config changes every 30 seconds
  const CHECK_INTERVAL = 30_000;
  let lastCheck = Date.now();

  return (req, res, next) => {
    const now = Date.now();
    if (now - lastCheck > CHECK_INTERVAL) {
      lastCheck = now;
      const newWindowMs = getConfigInt(windowMsKey, defaultWindowMs);
      const newMax = getConfigInt(maxKey, defaultMax);
      if (newWindowMs !== currentWindowMs || newMax !== currentMax) {
        currentWindowMs = newWindowMs;
        currentMax = newMax;
        limiter = buildLimiter(currentWindowMs, currentMax, message);
        console.log(`[RateLimit] ${windowMsKey.replace('.window_ms', '')} updated: max=${currentMax}, window=${currentWindowMs}ms`);
      }
    }
    limiter(req, res, next);
  };
}

/**
 * @param {number} windowMs
 * @param {number} max
 * @param {string} message
 * @returns {import('express').RequestHandler}
 */
function buildLimiter(windowMs, max, message) {
  return rateLimit({
    windowMs,
    max,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: message },
  });
}
