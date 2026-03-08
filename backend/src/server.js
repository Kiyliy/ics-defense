// @ts-check

import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { initDB } from './models/db.js';
import alertRoutes from './routes/alerts.js';
import analysisRoutes from './routes/analysis.js';
import dashboardRoutes from './routes/dashboard.js';
import approvalRoutes from './routes/approval.js';
import auditRoutes from './routes/audit.js';
import notificationsRoutes from './routes/notifications.js';
import { errorHandler } from './middleware/errorHandler.js';

dotenv.config();

const app = /** @type {any} */ (express());
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// ---------------------------------------------------------------------------
// Simple API key auth middleware (skip if API_AUTH_TOKEN not set — dev mode)
// ---------------------------------------------------------------------------
const API_AUTH_TOKEN = process.env.API_AUTH_TOKEN || '';

app.use((/** @type {any} */ req, /** @type {any} */ res, /** @type {() => void} */ next) => {
  // Allow health endpoint without auth
  if (req.path === '/api/health') return next();

  // If no token configured, skip auth (dev mode)
  if (!API_AUTH_TOKEN) return next();

  const authHeader = req.headers['authorization'] || '';
  const apiKeyHeader = req.headers['x-api-key'] || '';

  const bearerToken = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : '';
  const token = bearerToken || apiKeyHeader;

  if (token !== API_AUTH_TOKEN) {
    return res.status(401).json({ error: 'Unauthorized: invalid or missing API token' });
  }

  next();
});

const db = initDB(process.env.DB_PATH || './data/ics-defense.db');

app.use((/** @type {any} */ req, /** @type {any} */ _res, /** @type {() => void} */ next) => {
  req.db = db;
  next();
});

app.use('/api/alerts', alertRoutes);
app.use('/api/analysis', analysisRoutes);
app.use('/api/dashboard', dashboardRoutes);
app.use('/api/approval', approvalRoutes);
app.use('/api/audit', auditRoutes);
app.use('/api/notifications', notificationsRoutes);

app.get('/api/health', (/** @type {any} */ _req, /** @type {any} */ res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`ICS Defense Backend running on http://localhost:${PORT}`);
});
