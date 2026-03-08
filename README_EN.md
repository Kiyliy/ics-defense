# ICS Defense

> AI-driven industrial control system (ICS) security analysis and response platform.

This repository provides a demo platform for multi-source alert ingestion, correlation analysis, MITRE ATT&CK for ICS mapping, AI-assisted decision-making, audit logging, and approval-based response execution.

For the main documentation, please use the Chinese README:
- [`README.md`](./README.md)

## Highlights

- Multi-source alert ingestion
- Alert normalization and clustering
- MITRE ATT&CK for ICS mapping
- AI planning + tool use + structured final decision
- Strict structured outputs for xAI-compatible models
- MCP-based local tools
- Approval queue for risky actions
- Audit trail and token usage tracking
- Docker Compose full-stack deployment

## Stack

- FastAPI / Python
- Express / Node.js
- Vue 3 / Vite / Nginx
- SQLite / Redis
- MCP
- xAI / OpenAI-compatible APIs

## Run

```bash
docker compose up -d --build
```

## Notes

The Chinese README is the primary documentation source for this project.
