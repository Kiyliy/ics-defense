// @ts-check

import crypto from 'crypto';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import dotenv from 'dotenv';
import { initDB } from './models/db.js';
import alertRoutes from './routes/alerts.js';
import { createAnalysisRouter } from './routes/analysis.js';
import dashboardRoutes from './routes/dashboard.js';
import approvalRoutes from './routes/approval.js';
import auditRoutes from './routes/audit.js';
import { createNotificationsRouter } from './routes/notifications.js';
import { errorHandler } from './middleware/errorHandler.js';

dotenv.config();

const NODE_ENV = process.env.NODE_ENV || 'development';
const isProduction = NODE_ENV === 'production';

// ---------------------------------------------------------------------------
// Production safety: require API_AUTH_TOKEN in production
// ---------------------------------------------------------------------------
const API_AUTH_TOKEN = process.env.API_AUTH_TOKEN || '';
if (isProduction && !API_AUTH_TOKEN) {
  console.error('FATAL: API_AUTH_TOKEN must be set in production. Exiting.');
  process.exit(1);
}
if (!API_AUTH_TOKEN) {
  console.warn('WARNING: API_AUTH_TOKEN is not set — authentication is disabled (dev mode)');
}

const app = /** @type {any} */ (express());
const PORT = process.env.PORT || 3000;

// ---------------------------------------------------------------------------
// Security headers
// ---------------------------------------------------------------------------
app.use(helmet());

const allowedOrigins = (process.env.CORS_ORIGINS || 'http://localhost:5173,http://localhost:5174')
  .split(',')
  .map((o) => o.trim());
app.use(cors({ origin: allowedOrigins }));
app.use(express.json({ limit: '1mb' }));

// ---------------------------------------------------------------------------
// Rate limiting
// ---------------------------------------------------------------------------
const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 500,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests, please try again later' },
});
app.use('/api/', globalLimiter);

// Stricter limits for expensive endpoints (LLM, notifications)
const llmLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  message: { error: 'LLM rate limit exceeded, please try again later' },
});
const notifyLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 20,
  message: { error: 'Notification rate limit exceeded' },
});

// ---------------------------------------------------------------------------
// API key auth middleware
// ---------------------------------------------------------------------------
app.use((/** @type {any} */ req, /** @type {any} */ res, /** @type {() => void} */ next) => {
  // Allow health endpoint without auth
  if (req.path === '/api/health') return next();

  // If no token configured, skip auth (dev mode) — warning already logged at startup
  if (!API_AUTH_TOKEN) return next();

  const authHeader = req.headers['authorization'] || '';
  const apiKeyHeader = req.headers['x-api-key'] || '';

  const bearerToken = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : '';
  const token = bearerToken || apiKeyHeader;

  // Constant-time comparison to prevent timing attacks
  if (!token || !safeCompare(token, API_AUTH_TOKEN)) {
    return res.status(401).json({ error: 'Unauthorized: invalid or missing API token' });
  }

  next();
});

/**
 * Constant-time string comparison to prevent timing attacks
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

const db = initDB(process.env.DB_PATH || './data/ics-defense.db');

app.use((/** @type {any} */ req, /** @type {any} */ _res, /** @type {() => void} */ next) => {
  req.db = db;
  next();
});

app.use('/api/alerts', alertRoutes);
app.use('/api/analysis/alerts', llmLimiter);
app.use('/api/analysis/chat', llmLimiter);
app.use('/api/analysis', createAnalysisRouter());
app.use('/api/dashboard', dashboardRoutes);
app.use('/api/approval', approvalRoutes);
app.use('/api/audit', auditRoutes);
app.use('/api/notifications/test', notifyLimiter);
app.use('/api/notifications', createNotificationsRouter());

app.get('/api/health', (/** @type {any} */ _req, /** @type {any} */ res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.use(errorHandler);

// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------
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
