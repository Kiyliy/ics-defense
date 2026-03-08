import test from 'node:test';
import assert from 'node:assert/strict';
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

test('analysis alerts validates payload and missing alerts', async () => {
  await withTestServer(async ({ baseUrl }) => {
    const bad = await fetch(`${baseUrl}/api/analysis/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [] }),
    });
    assert.equal(bad.status, 400);
    assert.deepEqual(await bad.json(), { error: 'alert_ids[] required' });

    const badIds = await fetch(`${baseUrl}/api/analysis/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [0, 2] }),
    });
    assert.equal(badIds.status, 400);
    assert.deepEqual(await badIds.json(), { error: 'alert_ids must contain positive integers' });

    const missing = await fetch(`${baseUrl}/api/analysis/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [999] }),
    });
    assert.equal(missing.status, 404);
    assert.deepEqual(await missing.json(), { error: 'No alerts found' });
  });
});

test('analysis alerts rejects partial missing ids', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    seedAlerts(db);
    const response = await fetch(`${baseUrl}/api/analysis/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [1, 999] }),
    });

    assert.equal(response.status, 404);
    assert.deepEqual(await response.json(), {
      error: 'Some alerts were not found',
      missing_alert_ids: [999],
    });
  });
});

test('analysis alerts delegates to agent service and updates alert statuses', async () => {
  const mockFetch = async (url, options) => {
    assert.match(String(url), /\/analyze$/);
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { alert_ids: [1, 2] });
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
    assert.equal(response.status, 200);

    const body = await response.json();
    assert.equal(body.status, 'analyzing');
    assert.equal(body.message, 'Analysis delegated to Agent Service');
    assert.equal(body.trace_id, 'trace-123');

    const statuses = db.prepare('SELECT id, status FROM alerts ORDER BY id ASC').all();
    assert.deepEqual(statuses, [
      { id: 1, status: 'analyzing' },
      { id: 2, status: 'analyzing' },
    ]);
  }, createAnalysisRouter({ fetchFn: mockFetch }));
});

test('analysis chat endpoint validates messages payload', async () => {
  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/analysis/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: null }),
    });

    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: 'messages[] required' });
  });
});

test('analysis chains endpoint joins decisions and exposes nested data', async () => {
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
    assert.equal(chainsResp.status, 200);
    assert.equal(chains.chains.length, 1);
    assert.equal(chains.chains[0].alerts.length, 1);
    assert.equal(chains.chains[0].alert_count, 1);
    assert.equal(chains.chains[0].decisions.length, 2);
    assert.equal(chains.chains[0].decisions[0].action, 'block now');
    assert.equal(chains.chains[0].recommendation, 'block now');
    assert.equal(chains.chains[0].decision_status, 'pending');
  });
});

test('analysis decision patch returns 404 when decision is missing', async () => {
  await withTestServer(async ({ baseUrl }) => {
    const missingPatch = await fetch(`${baseUrl}/api/analysis/decisions/999`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'accepted' }),
    });
    assert.equal(missingPatch.status, 404);
    assert.deepEqual(await missingPatch.json(), { error: 'Decision not found' });
  });
});
