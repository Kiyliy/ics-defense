import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { initDB } from './models/db.js';
import alertRoutes from './routes/alerts.js';
import analysisRoutes from './routes/analysis.js';
import dashboardRoutes from './routes/dashboard.js';
import approvalRoutes from './routes/approval.js';
import auditRoutes from './routes/audit.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// 初始化数据库
const db = initDB(process.env.DB_PATH || './data/ics-defense.db');

// 注入 db 到请求上下文
app.use((req, _res, next) => {
  req.db = db;
  next();
});

// API 路由
app.use('/api/alerts', alertRoutes);
app.use('/api/analysis', analysisRoutes);
app.use('/api/dashboard', dashboardRoutes);
app.use('/api/approval', approvalRoutes);
app.use('/api/audit', auditRoutes);

// 健康检查
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`ICS Defense Backend running on http://localhost:${PORT}`);
});
