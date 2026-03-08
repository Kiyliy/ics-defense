# ICS Defense

> 面向工控安全场景的 AI 驱动告警分析与响应平台。

ICS Defense 是一个用于工控安全（ICS Security）场景的端到端演示平台，支持多源安全告警接入、标准化与聚合、MITRE ATT&CK for ICS 映射、AI 分析决策、审计追踪，以及基于审批的响应执行。

项目由以下核心部分组成：
- Python `Agent Service`：负责规划式分析、工具调用和结构化决策输出
- Node.js `Backend API`：负责业务 API、数据落库、审批流与审计查询
- Vue 3 `Frontend`：负责大屏展示、分析结果查看和运维操作
- 本地 `MCP tools`：负责日志检索、规则匹配、知识查询、记忆、通知和动作执行

English version: [`README_EN.md`](./README_EN.md)

## 功能特性

- 多源告警接入：支持 `waf`、`nids`、`hids`、`pikachu`、`soc`
- 告警标准化与聚合分析
- MITRE ATT&CK for ICS 战术 / 技术映射
- AI 驱动的 Planning + Tool Use + Structured Decision 分析链路
- 基于严格 JSON Schema 的结构化输出
- MCP 工具扩展体系：
  - 日志检索
  - 关联规则匹配
  - MITRE 知识库查询
  - 记忆检索与存储
  - 通知发送
  - 响应动作执行
- 高风险动作审批流
- 审计日志与 Token 使用量统计
- 基于 Docker Compose 的整套部署方式

## 架构概览

```text
Frontend (Vue 3 + Vite + Nginx)
          |
          v
Backend API (Express + SQLite)
          |
          v
Agent Service (FastAPI + xAI/OpenAI-compatible API)
          |
          +--> MCP: log-search
          +--> MCP: rule-engine
          +--> MCP: mitre-kb
          +--> MCP: memory
          +--> MCP: notifier
          +--> MCP: action-executor
          |
          v
SQLite / Redis
```

## 目录结构

```text
.
├── agent/                # Python Agent 核心、提示词、策略、服务入口
├── backend/              # Express 后端 API
├── frontend/             # Vue 3 前端
├── collector/            # 告警标准化 / 聚合辅助模块
├── mcp-servers/          # 本地 MCP 工具服务
├── tests/                # Python 测试集
├── docker-compose.yml    # 全栈部署编排
├── Dockerfile.agent
├── Dockerfile.backend
├── Dockerfile.frontend
└── nginx.conf
```

## 技术栈

### 后端 / Agent
- Python 3.12
- FastAPI
- OpenAI-compatible SDK（用于对接 xAI）
- MCP Python SDK
- SQLite
- Redis
- Node.js + Express
- better-sqlite3

### 前端
- Vue 3
- Vite
- Vue Router
- Axios
- ECharts
- Nginx

## 快速开始

### 1. 配置环境变量

当前项目使用 `backend/.env` 作为 Docker Compose 的共享运行时环境文件。

示例：

```env
PORT=3002
XAI_API_KEY=your_xai_api_key
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-3-mini-fast
DB_PATH=./data/ics-defense.db
```

Docker Compose 启动时最关键的变量有：
- `XAI_API_KEY`
- `XAI_BASE_URL`
- `XAI_MODEL`
- `NOTIFICATION_PROVIDER`
- `FEISHU_BOT_WEBHOOK_URL`（启用飞书机器人时）
- `FEISHU_BOT_SECRET`（飞书开启签名校验时）
- `FEISHU_APP_ID`（飞书应用机器人）
- `FEISHU_APP_SECRET`（飞书应用机器人）
- `FEISHU_APP_RECEIVE_ID`（默认接收对象，如 chat_id）
- `FEISHU_APP_RECEIVE_ID_TYPE`（默认 `chat_id`）

如果宿主机端口冲突，也可以在启动时覆盖：
- `REDIS_PORT`
- `AGENT_SERVICE_PORT`
- `BACKEND_PORT`
- `FRONTEND_PORT`

### 2. 使用 Docker Compose 启动

```bash
REDIS_PORT=6379 \
AGENT_SERVICE_PORT=8000 \
BACKEND_PORT=3000 \
FRONTEND_PORT=80 \
docker compose up -d --build
```

### 3. 健康检查

```bash
curl http://localhost:8000/status
curl http://localhost:3000/api/health
curl http://localhost/api/health
```

## Docker Compose 结构说明

当前 Compose 结构如下：

- `redis`
  - Redis Streams / 缓冲与消息能力
- `agent-service`
  - FastAPI AI 分析服务
  - 对接 xAI 兼容接口
  - 通过 stdio 启动本地 MCP 工具
- `backend`
  - Express 业务 API
  - 负责告警、审批、审计、攻击链与处置建议持久化
  - 向 `agent-service` 发起分析请求
- `frontend`
  - Nginx 托管前端静态资源
  - 将 `/api` 代理到 `backend`

### 当前结构的优点

- 职责边界清晰
- Agent 与业务 API 解耦
- 前端保持无状态，部署简单
- `backend` 与 `agent-service` 共享 SQLite 数据
- MCP 工具内聚在 Agent 侧，结构直观，适合演示与论文项目

### 当前结构的取舍

- SQLite 简单易用，但高并发场景不是最优解
- MCP 工具和 Agent 放在一个容器内，部署简单，但横向扩展灵活性一般
- Compose 更偏生产演示；前端热更新开发仍然更适合本地直跑

### 推荐的后续演进方向

如果项目继续扩展，比较自然的升级路线是：
- 保持 `frontend`、`backend`、`agent-service`、`redis` 四层结构
- 把 SQLite 升级到 PostgreSQL
- 将高价值 MCP 工具拆分成独立服务
- 为本地开发增加 `docker-compose.override.yml`

## 主要工作流

### 告警接入

```bash
curl -X POST http://localhost:3000/api/alerts/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "waf",
    "events": [
      {
        "rule_name": "SQL Injection Detected",
        "severity": "high",
        "src_ip": "192.168.1.100",
        "dst_ip": "10.0.0.5",
        "reason": "Detected SQL injection pattern in POST /login"
      }
    ]
  }'
```

### 触发 AI 分析

```bash
curl -X POST http://localhost:3000/api/analysis/alerts \
  -H 'Content-Type: application/json' \
  -d '{"alert_ids": [1,2,3]}'
```

### 轮询分析结果

```bash
curl http://localhost:8000/analyze/<trace_id>
```

### 查询攻击链

```bash
curl http://localhost:3000/api/analysis/chains
```

### 发送通知测试

```bash
curl -X POST http://localhost:3000/api/notifications/test \
  -H 'Content-Type: application/json' \
  -d '{
    "provider": "feishu",
    "text": "ICS Defense 通知链路测试"
  }'
```

返回 `202 Accepted` 代表消息已写入 Redis Streams，随后由 `ics-notification-worker` 异步消费并发送到飞书。

### 发送告警到飞书机器人

```bash
curl -X POST http://localhost:3000/api/notifications/alerts/1/send \
  -H 'Content-Type: application/json' \
  -d '{"provider":"feishu"}'
```

## 结构化输出设计

本项目的 AI 分析链路默认采用严格结构化输出。

核心设计点：
- 规划阶段输出受 JSON Schema 约束
- 最终结论输出受 JSON Schema 约束
- 旧式文本/Markdown 提取仅保留为兜底逻辑
- 避免依赖从 Markdown code block 中抠 JSON 的脆弱方案

这种设计对以下场景更稳定：
- 自动化流程编排
- 审计与追踪
- 数据库存储
- 前端结果渲染

## 主要 API

### Backend
- `GET /api/health`
- `POST /api/alerts/ingest`
- `GET /api/alerts`
- `POST /api/analysis/alerts`
- `POST /api/analysis/chat`
- `GET /api/analysis/chains`
- `GET /api/approval`
- `PATCH /api/approval/:id`
- `GET /api/audit`
- `GET /api/audit/stats`
- `GET /api/notifications/providers`
- `POST /api/notifications/test`
- `POST /api/notifications/alerts/:id/send`

### Agent Service
- `GET /status`
- `POST /analyze`
- `GET /analyze/{trace_id}`
- `POST /chat`
- `POST /approval/{approval_id}/respond`

## 本地开发

### PM2 管理约定

- 当前开发环境中的后端服务由 `PM2` 管理，进程名为 `ics-backend`
- 修改 `backend/.env` 或后端代码后，优先执行 `pm2 restart ics-backend --update-env`
- 不要额外手工启动新的 `node src/server.js` 实例，避免端口 `3002` 冲突
- 常用检查命令：`pm2 list`、`pm2 describe ics-backend`、`pm2 logs ics-backend --lines 100`、`pm2 logs ics-notification-worker --lines 100`

### Backend

```bash
cd backend
npm install
npm run dev
```

### Notification Worker

```bash
cd backend
npm run worker:notifications
```

### PM2（推荐）

```bash
cd backend
pm2 start ecosystem.config.cjs --only ics-notification-worker
pm2 restart ics-backend --update-env
pm2 restart ics-notification-worker --update-env
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Agent Service

```bash
python3 -m uvicorn agent.service:app --host 0.0.0.0 --port 8000
```

## 测试

Python 测试：

```bash
pytest
```

Compose 配置校验：

```bash
docker compose config
```

## 安全说明

- 不要提交真实密钥
- `backend/.env` 已被 Git 忽略
- 高风险动作应始终保留审批机制
- 如果已经公开过真实凭证，建议在正式开源前立即轮换密钥

## Roadmap

- 将 SQLite 升级为 PostgreSQL
- 增加浏览器端 e2e 测试
- 优化前端构建产物拆包
- 增强攻击链可视化效果
- 增加开发环境专用的 Compose 覆盖配置
- 接入 CI 做测试、构建与镜像校验

## 许可证

请根据你的开源发布计划补充正式 License。

## 致谢

本项目构建于以下基础之上：
- FastAPI
- Express
- Vue 3
- Docker Compose
- MCP
- xAI / OpenAI-compatible APIs
