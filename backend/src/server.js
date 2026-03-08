// @ts-check

import crypto from 'crypto';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import dotenv from 'dotenv';
import { initDB } from './models/db.js';
import { initConfigService, getConfig } from './services/config.js';
import { createDynamicRateLimiter } from './middleware/dynamicRateLimit.js';
import alertRoutes from './routes/alerts.js';
import { createAnalysisRouter } from './routes/analysis.js';
import dashboardRoutes from './routes/dashboard.js';
import approvalRoutes from './routes/approval.js';
import auditRoutes from './routes/audit.js';
import configRoutes from './routes/config.js';
import { createNotificationsRouter } from './routes/notifications.js';
import { errorHandler } from './middleware/errorHandler.js';

dotenv.config();

// ===========================================================================
// 部署/基础设施参数 — 始终从环境变量读取
// ===========================================================================
const NODE_ENV = process.env.NODE_ENV || 'development';
const isProduction = NODE_ENV === 'production';
const PORT = process.env.PORT || 3000;
const API_AUTH_TOKEN = process.env.API_AUTH_TOKEN || '';

if (isProduction && !API_AUTH_TOKEN) {
  console.error('FATAL: API_AUTH_TOKEN must be set in production. Exiting.');
  process.exit(1);
}
if (!API_AUTH_TOKEN) {
  console.warn('WARNING: API_AUTH_TOKEN is not set — authentication is disabled (dev mode)');
}

// ===========================================================================
// Database & config service
// ===========================================================================
const db = initDB(process.env.DB_PATH || './data/ics-defense.db');
initConfigService(db);

// ===========================================================================
// Express app
// ===========================================================================
const app = /** @type {any} */ (express());

// Security headers
app.use(helmet());

const allowedOrigins = (process.env.CORS_ORIGINS || 'http://localhost:5173,http://localhost:5174')
  .split(',')
  .map((o) => o.trim());
app.use(cors({ origin: allowedOrigins }));

// Body limit — read from config at startup (restart required to change)
const bodyLimit = getConfig('request.body_limit', '1mb');
app.use(express.json({ limit: bodyLimit }));

// ===========================================================================
// 速率限制 — 业务参数从 system_config 表动态读取，可通过 API 调整
// ===========================================================================
const globalLimiter = createDynamicRateLimiter({
  windowMsKey: 'rate_limit.global.window_ms',
  maxKey: 'rate_limit.global.max',
  defaultWindowMs: 900_000,
  defaultMax: 500,
  message: 'Too many requests, please try again later',
});

const llmLimiter = createDynamicRateLimiter({
  windowMsKey: 'rate_limit.llm.window_ms',
  maxKey: 'rate_limit.llm.max',
  defaultWindowMs: 60_000,
  defaultMax: 10,
  message: 'LLM rate limit exceeded, please try again later',
});

const notifyLimiter = createDynamicRateLimiter({
  windowMsKey: 'rate_limit.notify.window_ms',
  maxKey: 'rate_limit.notify.max',
  defaultWindowMs: 60_000,
  defaultMax: 20,
  message: 'Notification rate limit exceeded',
});

app.use('/api/', globalLimiter);

// ===========================================================================
// Auth middleware
// ===========================================================================
app.use((/** @type {any} */ req, /** @type {any} */ res, /** @type {() => void} */ next) => {
  if (req.path === '/api/health') return next();
  if (!API_AUTH_TOKEN) return next();

  const authHeader = req.headers['authorization'] || '';
  const apiKeyHeader = req.headers['x-api-key'] || '';
  const bearerToken = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : '';
  const token = bearerToken || apiKeyHeader;

  if (!token || !safeCompare(token, API_AUTH_TOKEN)) {
    return res.status(401).json({ error: 'Unauthorized: invalid or missing API token' });
  }
  next();
});

/**
 * @param {string} a
 * @param {string} b
 * @returns {boolean}
 */
function safeCompare(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

// ===========================================================================
// Inject db
// ===========================================================================
app.use((/** @type {any} */ req, /** @type {any} */ _res, /** @type {() => void} */ next) => {
  req.db = db;
  next();
});

// ===========================================================================
// Routes
// ===========================================================================
app.use('/api/alerts', alertRoutes);
app.use('/api/analysis/alerts', llmLimiter);
app.use('/api/analysis/chat', llmLimiter);
app.use('/api/analysis', createAnalysisRouter());
app.use('/api/dashboard', dashboardRoutes);
app.use('/api/approval', approvalRoutes);
app.use('/api/audit', auditRoutes);
app.use('/api/config', configRoutes);
app.use('/api/notifications/test', notifyLimiter);
app.use('/api/notifications', createNotificationsRouter());

app.get('/api/health', (/** @type {any} */ _req, /** @type {any} */ res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.use(errorHandler);

// ===========================================================================
// Start & graceful shutdown
// ===========================================================================
const server = app.listen(PORT, () => {
  console.log(`ICS Defense Backend running on http://localhost:${PORT} [${NODE_ENV}]`);
});

function gracefulShutdown(signal) {
  console.log(`\n${signal} received. Shutting down gracefully...`);
  server.close(() => {
    db.close();
    console.log('Database closed. Bye.');
    process.exit(0);
  });
}
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
