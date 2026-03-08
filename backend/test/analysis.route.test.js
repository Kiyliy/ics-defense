import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import express from 'express';
import { initDB } from '../src/models/db.js';
import { createAnalysisRouter } from '../src/routes/analysis.js';

async function withTestServer(run, options = {}) {
  const tempDir = mkdtempSync(join(tmpdir(), 'ics-defense-analysis-'));
  const db = initDB(join(tempDir, 'data', 'test.db'));
  const app = express();
  const originalFetch = global.fetch;

  if (options.externalFetch) {
    global.fetch = options.externalFetch;
  }

  const analysisRouter = createAnalysisRouter();
  app.use(express.json());
  app.use((req, _res, next) => {
    req.db = db;
    next();
  });
  app.use('/api/analysis', analysisRouter);

  const server = await new Promise((resolve) => {
    const instance = app.listen(0, () => resolve(instance));
  });
  const baseUrl = `http://127.0.0.1:${server.address().port}`;

  try {
    await run({ db, baseUrl, fetchJson: (url, init) => originalFetch(url, init) });
  } finally {
    global.fetch = originalFetch;
    await new Promise((resolve, reject) => server.close((err) => (err ? reject(err) : resolve())));
    db.close();
    rmSync(tempDir, { recursive: true, force: true });
  }
}

test('analysis alerts endpoint validates payload and missing alerts', async () => {
  await withTestServer(async ({ baseUrl, fetchJson }) => {
    const bad = await fetchJson(`${baseUrl}/api/analysis/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [] }),
    });
    assert.equal(bad.status, 400);
    assert.deepEqual(await bad.json(), { error: 'alert_ids[] required' });

    const missing = await fetchJson(`${baseUrl}/api/analysis/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [999] }),
    });
    assert.equal(missing.status, 404);
    assert.deepEqual(await missing.json(), { error: 'No alerts found' });
  });
});

test('analysis alerts delegates to agent service and updates alert statuses', async () => {
  await withTestServer(async ({ db, baseUrl, fetchJson }) => {
    const insert = db.prepare(`
      INSERT INTO alerts (source, severity, title, status)
      VALUES (?, ?, ?, ?)
    `);
    insert.run('waf', 'high', 'SQL Injection', 'open');
    insert.run('nids', 'critical', 'RCE Attempt', 'open');

    const response = await fetchJson(`${baseUrl}/api/analysis/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [1, 2] }),
    });
    assert.equal(response.status, 200);

    const body = await response.json();
    assert.equal(body.status, 'analyzing');
    assert.equal(body.message, 'Analysis delegated to Agent Service');
    assert.equal(typeof body.trace_id, 'string');
    assert.ok(body.trace_id.length > 0);

    const statuses = db.prepare('SELECT id, status FROM alerts ORDER BY id ASC').all();
    assert.deepEqual(statuses, [
      { id: 1, status: 'analyzing' },
      { id: 2, status: 'analyzing' },
    ]);
  }, {
    externalFetch: async (url, options) => {
      assert.match(String(url), /\/analyze$/);
      assert.equal(options.method, 'POST');
      assert.deepEqual(JSON.parse(options.body), { alert_ids: [1, 2] });
      return {
        ok: true,
        async json() {
          return { trace_id: 'trace-123' };
        },
      };
    },
  });
});

test('analysis alerts fallback resolves alerts when agent service is unavailable', async () => {
  await withTestServer(async ({ db, baseUrl, fetchJson }) => {
    const insert = db.prepare(`
      INSERT INTO alerts (source, severity, title, status)
      VALUES (?, ?, ?, ?)
    `);
    insert.run('waf', 'high', 'SQL Injection', 'open');

    const response = await fetchJson(`${baseUrl}/api/analysis/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [1] }),
    });
    assert.equal(response.status, 200);

    const body = await response.json();
    assert.equal(body.attack_chain_id, 1);
    assert.equal(body.analysis.risk_level, 'high');

    const alert = db.prepare('SELECT status FROM alerts WHERE id = 1').get();
    assert.equal(alert.status, 'resolved');
  }, {
    externalFetch: async () => {
      throw new Error('agent down');
    },
  });
});

test('analysis chat endpoint validates messages payload', async () => {
  await withTestServer(async ({ baseUrl, fetchJson }) => {
    const response = await fetchJson(`${baseUrl}/api/analysis/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: null }),
    });

    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: 'messages[] required' });
  });
});

test('analysis chains endpoint joins decisions and decisions patch validates states', async () => {
  await withTestServer(async ({ db, baseUrl, fetchJson }) => {
    const chainId = Number(db.prepare(`
      INSERT INTO attack_chains (name, stage, confidence, alert_ids, evidence)
      VALUES ('Chain-1', 'Execution', 0.81, '[1,2]', 'evidence')
    `).run().lastInsertRowid);

    const decisionId = Number(db.prepare(`
      INSERT INTO decisions (attack_chain_id, risk_level, recommendation, action_type, rationale, status)
      VALUES (?, 'high', 'block now', 'block', 'because', 'pending')
    `).run(chainId).lastInsertRowid);

    const chainsResp = await fetchJson(`${baseUrl}/api/analysis/chains`);
    const chains = await chainsResp.json();
    assert.equal(chainsResp.status, 200);
    assert.equal(chains.chains.length, 1);
    assert.equal(chains.chains[0].recommendation, 'block now');
    assert.equal(chains.chains[0].action_type, 'block');
    assert.equal(chains.chains[0].decision_status, 'pending');
    assert.equal(chains.chains[0].risk_level, 'high');

    const invalidPatch = await fetchJson(`${baseUrl}/api/analysis/decisions/${decisionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'pending' }),
    });
    assert.equal(invalidPatch.status, 400);

    const validPatch = await fetchJson(`${baseUrl}/api/analysis/decisions/${decisionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'accepted' }),
    });
    assert.equal(validPatch.status, 200);
    assert.deepEqual(await validPatch.json(), { updated: true });

    const missingPatch = await fetchJson(`${baseUrl}/api/analysis/decisions/99999`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'accepted' }),
    });
    assert.equal(missingPatch.status, 404);
    assert.deepEqual(await missingPatch.json(), { error: 'Decision not found' });

    const decision = db.prepare('SELECT status FROM decisions WHERE id = ?').get(decisionId);
    assert.equal(decision.status, 'accepted');
  });
});
