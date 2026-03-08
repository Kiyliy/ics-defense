# ICS Defense

> AI-driven industrial control system (ICS) security analysis and response platform.

ICS Defense is an end-to-end demo platform for multi-source security alert ingestion, correlation analysis, MITRE ATT&CK for ICS mapping, AI-assisted decision-making, audit logging, and approval-based response execution.

It combines:
- a Python `Agent Service` for plan-and-execute analysis,
- a Node.js `Backend API` for business APIs and persistence,
- a Vue 3 `Frontend` for dashboard and analyst workflows,
- a set of local `MCP tools` for log search, rule matching, memory, notification, and action execution.

## Features

- Multi-source alert ingestion (`waf`, `nids`, `hids`, `pikachu`, `soc`)
- Alert normalization and clustering
- MITRE ATT&CK for ICS tactic / technique mapping
- AI-based planning + tool use + final structured decision generation
- Structured outputs with strict JSON schema for xAI-compatible models
- MCP-based local tools:
  - log search
  - rule engine
  - MITRE knowledge base
  - memory
  - notifier
  - action executor
- Approval queue for high-risk response operations
- Full audit trail with token usage tracking
- Docker Compose deployment for the full stack

## Architecture

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

## Repository Structure

```text
.
├── agent/                # Python agent core, prompts, policies, service
├── backend/              # Express backend API
├── frontend/             # Vue 3 frontend
├── collector/            # Alert normalization / clustering helpers
├── mcp-servers/          # Local MCP tool servers
├── tests/                # Python test suite
├── docker-compose.yml    # Full-stack deployment
├── Dockerfile.agent
├── Dockerfile.backend
├── Dockerfile.frontend
└── nginx.conf
```

## Tech Stack

### Backend / Agent
- Python 3.12
- FastAPI
- OpenAI-compatible SDK (`openai`) for xAI access
- MCP Python SDK
- SQLite
- Redis
- Node.js + Express
- better-sqlite3

### Frontend
- Vue 3
- Vite
- Vue Router
- Axios
- ECharts
- Nginx

## Quick Start

### 1. Configure environment

The project uses `backend/.env` as the shared runtime environment file for Docker Compose.

Example:

```env
PORT=3002
XAI_API_KEY=your_xai_api_key
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-3-mini-fast
DB_PATH=./data/ics-defense.db
```

For Docker Compose, the most important variables are:
- `XAI_API_KEY`
- `XAI_BASE_URL`
- `XAI_MODEL`

Optional host port overrides can be supplied when starting Compose:
- `REDIS_PORT`
- `AGENT_SERVICE_PORT`
- `BACKEND_PORT`
- `FRONTEND_PORT`

### 2. Start with Docker Compose

```bash
REDIS_PORT=6379 \
AGENT_SERVICE_PORT=8000 \
BACKEND_PORT=3000 \
FRONTEND_PORT=80 \
docker compose up -d --build
```

### 3. Verify services

```bash
curl http://localhost:8000/status
curl http://localhost:3000/api/health
curl http://localhost/api/health
```

## Docker Compose Topology

Current Compose structure:

- `redis`
  - Redis Streams / shared queue support
- `agent-service`
  - FastAPI-based AI analysis service
  - connects to xAI-compatible API
  - starts MCP servers via stdio
- `backend`
  - Express API
  - persists alerts, decisions, audit logs, attack chains
  - proxies analysis requests to `agent-service`
- `frontend`
  - Nginx-served production frontend
  - proxies `/api` requests to `backend`

### Why this structure is good

- Clear separation of responsibilities
- Agent and business API are decoupled
- Frontend stays stateless and easy to deploy
- SQLite is shared between `backend` and `agent-service`
- MCP tools remain local to the agent instead of becoming extra containers

### Current trade-offs

- SQLite is simple and portable, but not ideal for high concurrency
- MCP tools live inside the agent container, which is simple but less independently scalable
- Frontend is production-oriented in Compose; live dev workflow still fits better outside Compose

### Recommended future evolution

If the project grows, a natural next step would be:
- keep `frontend`, `backend`, `agent-service`, `redis`
- move SQLite to PostgreSQL
- optionally split high-value MCP tools into standalone services
- add `docker-compose.override.yml` for local dev ergonomics

## Main Workflows

### Alert Ingestion

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

### Trigger AI Analysis

```bash
curl -X POST http://localhost:3000/api/analysis/alerts \
  -H 'Content-Type: application/json' \
  -d '{"alert_ids": [1,2,3]}'
```

### Poll Analysis Result

```bash
curl http://localhost:8000/analyze/<trace_id>
```

### Query Attack Chains

```bash
curl http://localhost:3000/api/analysis/chains
```

## Structured Output Design

This project uses strict structured outputs for AI analysis.

Key points:
- planning output is schema-constrained JSON
- final decision output is schema-constrained JSON
- fallback text parsing is kept only as a last resort
- this avoids fragile extraction from Markdown code blocks

This design improves reliability for:
- automation
- auditability
- downstream persistence
- UI rendering

## Key API Endpoints

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

### Agent Service
- `GET /status`
- `POST /analyze`
- `GET /analyze/{trace_id}`
- `POST /chat`
- `POST /approval/{approval_id}/respond`

## Development

### Backend

```bash
cd backend
npm install
npm run dev
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

## Testing

Python tests:

```bash
pytest
```

Compose config validation:

```bash
docker compose config
```

## Security Notes

- Do **not** commit real secrets
- `backend/.env` is ignored by Git
- High-risk actions should stay approval-gated
- If publishing this project publicly, rotate any previously exposed credentials before sharing

## Roadmap

- Replace SQLite with PostgreSQL for multi-user concurrency
- Add browser-based e2e tests
- Improve frontend bundle splitting
- Add richer attack chain visualization
- Add dev-specific Compose overrides
- Add CI for linting, tests, and image builds

## License

Add your preferred open-source license here.

## Acknowledgements

Built around:
- FastAPI
- Express
- Vue 3
- Docker Compose
- MCP
- xAI / OpenAI-compatible APIs
