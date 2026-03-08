import { describe, it, expect } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import express from 'express';
import { createAnalysisRouter } from '../src/routes/analysis.js';
import { initDB } from '../src/models/db.js';

async function withTestServer(run, router = createAnalysisRouter()) {
  const tempDir = mkdtempSync(join(tmpdir(), 'ics-defense-analysis-'));
  const db = initDB(join(tempDir, 'data', 'test.db'));
  const app = express();
  app.use(express.json());
  app.use((req, _res, next) => {
    req.db = db;
    next();
  });
  app.use('/api/analysis', router);

  const server = await new Promise((resolve) => {
    const instance = app.listen(0, () => resolve(instance));
  });

  try {
    await run({ db, baseUrl: `http://127.0.0.1:${server.address().port}` });
  } finally {
    await new Promise((resolve, reject) => server.close((err) => (err ? reject(err) : resolve())));
    db.close();
    rmSync(tempDir, { recursive: true, force: true });
  }
}

function seedAlerts(db) {
  const insert = db.prepare(`
    INSERT INTO alerts (source, severity, title, description, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  insert.run('waf', 'high', 'SQL Injection', 'payload', 'open', '2026-03-08T10:00:00.000Z');
  insert.run('nids', 'critical', 'Port Scan', 'scan', 'open', '2026-03-08T10:05:00.000Z');
}

describe('analysis routes', () => {
  it('analysis alerts validates payload and missing alerts', async () => {
    await withTestServer(async ({ baseUrl }) => {
      const bad = await fetch(`${baseUrl}/api/analysis/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_ids: [] }),
      });
      expect(bad.status).toBe(400);
      expect(await bad.json()).toEqual({ error: 'alert_ids[] required' });

      const badIds = await fetch(`${baseUrl}/api/analysis/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_ids: [0, 2] }),
      });
      expect(badIds.status).toBe(400);
      expect(await badIds.json()).toEqual({ error: 'alert_ids must contain positive integers' });

      const missing = await fetch(`${baseUrl}/api/analysis/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_ids: [999] }),
      });
      expect(missing.status).toBe(404);
      expect(await missing.json()).toEqual({ error: 'No alerts found' });
    });
  });

  it('analysis alerts rejects partial missing ids', async () => {
    await withTestServer(async ({ db, baseUrl }) => {
      seedAlerts(db);
      const response = await fetch(`${baseUrl}/api/analysis/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_ids: [1, 999] }),
      });

      expect(response.status).toBe(404);
      expect(await response.json()).toEqual({
        error: 'Some alerts were not found',
        missing_alert_ids: [999],
      });
    });
  });

  it('analysis agent status proxies backend request', async () => {
    const mockFetch = async (url, options) => {
      expect(String(url)).toMatch(/\/status$/);
      expect(options.method).toBe('GET');
      expect(options.headers).toEqual({ Accept: 'application/json' });
      return {
        ok: true,
        async json() {
          return { status: 'ok', mcp_connected: true, mcp_servers: ['memory'], running_tasks: 2 };
        },
      };
    };

    await withTestServer(async ({ baseUrl }) => {
      const response = await fetch(`${baseUrl}/api/analysis/agent/status`);
      expect(response.status).toBe(200);
      expect(await response.json()).toEqual({
        status: 'ok',
        mcp_connected: true,
        mcp_servers: ['memory'],
        running_tasks: 2,
      });
    }, createAnalysisRouter({ fetchFn: mockFetch }));
  });

  it('analysis agent status returns 503 when upstream agent is unavailable', async () => {
    const mockFetch = async () => ({
      ok: false,
      status: 503,
      async text() {
        return 'agent down';
      },
    });

    await withTestServer(async ({ baseUrl }) => {
      const response = await fetch(`${baseUrl}/api/analysis/agent/status`);
      expect(response.status).toBe(503);
      expect(await response.json()).toEqual({
        error: 'Agent status unavailable',
        detail: 'Agent Service returned 503: agent down',
      });
    }, createAnalysisRouter({ fetchFn: mockFetch }));
  });

  it('analysis alerts delegates to agent service and updates alert statuses', async () => {
    const mockFetch = async (url, options) => {
      expect(String(url)).toMatch(/\/analyze$/);
      expect(options.method).toBe('POST');
      expect(JSON.parse(options.body)).toEqual({ alert_ids: [1, 2] });
      return {
        ok: true,
        async json() {
          return { trace_id: 'trace-123' };
        },
      };
    };

    await withTestServer(async ({ db, baseUrl }) => {
      seedAlerts(db);
      const response = await fetch(`${baseUrl}/api/analysis/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_ids: [1, 2] }),
      });
      expect(response.status).toBe(200);

      const body = await response.json();
      expect(body.status).toBe('analyzing');
      expect(body.message).toBe('Analysis delegated to Agent Service');
      expect(body.trace_id).toBe('trace-123');

      const statuses = db.prepare('SELECT id, status FROM alerts ORDER BY id ASC').all();
      expect(statuses).toEqual([
        { id: 1, status: 'analyzing' },
        { id: 2, status: 'analyzing' },
      ]);
    }, createAnalysisRouter({ fetchFn: mockFetch }));
  });

  it('analysis chat endpoint validates messages payload', async () => {
    await withTestServer(async ({ baseUrl }) => {
      const response = await fetch(`${baseUrl}/api/analysis/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: null }),
      });

      expect(response.status).toBe(400);
      expect(await response.json()).toEqual({ error: 'messages[] required' });
    });
  });

  it('analysis chains endpoint joins decisions and exposes nested data', async () => {
    await withTestServer(async ({ db, baseUrl }) => {
      db.prepare(`
        INSERT INTO alerts (id, source, severity, title, src_ip, status)
        VALUES (1, 'waf', 'high', 'SQL Injection', '10.0.0.1', 'resolved')
      `).run();

      const chainId = Number(db.prepare(`
        INSERT INTO attack_chains (name, stage, confidence, alert_ids, evidence)
        VALUES ('Chain-1', 'Execution', 0.81, '[1]', 'evidence')
      `).run().lastInsertRowid);

      db.prepare(`
        INSERT INTO decisions (attack_chain_id, risk_level, recommendation, action_type, rationale, status, created_at)
        VALUES (?, 'high', 'block now', 'block', 'because', 'pending', '2026-03-08T10:00:00.000Z')
      `).run(chainId);
      db.prepare(`
        INSERT INTO decisions (attack_chain_id, risk_level, recommendation, action_type, rationale, status, created_at)
        VALUES (?, 'medium', 'older rec', 'monitor', 'older', 'accepted', '2026-03-08T09:00:00.000Z')
      `).run(chainId);

      const chainsResp = await fetch(`${baseUrl}/api/analysis/chains`);
      const chains = await chainsResp.json();
      expect(chainsResp.status).toBe(200);
      expect(chains.chains.length).toBe(1);
      expect(chains.chains[0].alerts.length).toBe(1);
      expect(chains.chains[0].alert_count).toBe(1);
      expect(chains.chains[0].decisions.length).toBe(2);
      expect(chains.chains[0].decisions[0].action).toBe('block now');
      expect(chains.chains[0].recommendation).toBe('block now');
      expect(chains.chains[0].decision_status).toBe('pending');
    });
  });

  it('analysis decision patch returns 404 when decision is missing', async () => {
    await withTestServer(async ({ baseUrl }) => {
      const missingPatch = await fetch(`${baseUrl}/api/analysis/decisions/999`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'accepted' }),
      });
      expect(missingPatch.status).toBe(404);
      expect(await missingPatch.json()).toEqual({ error: 'Decision not found' });
    });
  });
});
