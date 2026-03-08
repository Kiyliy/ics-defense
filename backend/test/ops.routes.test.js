import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import express from 'express';
import approvalRouter from '../src/routes/approval.js';
import auditRouter from '../src/routes/audit.js';
import dashboardRouter from '../src/routes/dashboard.js';
import { initDB } from '../src/models/db.js';

async function withTestServer(run) {
  const tempDir = mkdtempSync(join(tmpdir(), 'ics-defense-ops-'));
  const db = initDB(join(tempDir, 'data', 'test.db'));
  const app = express();
  app.use(express.json());
  app.use((req, _res, next) => {
    req.db = db;
    next();
  });
  app.use('/api/approval', approvalRouter);
  app.use('/api/audit', auditRouter);
  app.use('/api/dashboard', dashboardRouter);

  const server = await new Promise((resolve) => {
    const instance = app.listen(0, () => resolve(instance));
  });
  const baseUrl = `http://127.0.0.1:${server.address().port}`;

  try {
    await run({ db, baseUrl });
  } finally {
    await new Promise((resolve, reject) => server.close((err) => (err ? reject(err) : resolve())));
    db.close();
    rmSync(tempDir, { recursive: true, force: true });
  }
}

test('approval routes filter pending items and persist one-time decisions', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    const insert = db.prepare(`
      INSERT INTO approval_queue (trace_id, tool_name, tool_args, reason, status)
      VALUES (?, ?, ?, ?, ?)
    `);
    insert.run('trace-1', 'block_ip', '{"ip":"10.0.0.8"}', 'block attacker', 'pending');
    insert.run('trace-2', 'send_email', '{"target":"soc"}', 'notify team', 'approved');

    const listResponse = await fetch(`${baseUrl}/api/approval?status=pending`);
    const listBody = await listResponse.json();

    assert.equal(listResponse.status, 200);
    assert.equal(listBody.total, 1);
    assert.equal(listBody.approvals[0].trace_id, 'trace-1');

    const approvalId = listBody.approvals[0].id;
    const patchResponse = await fetch(`${baseUrl}/api/approval/${approvalId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'rejected', reason: 'needs analyst review' }),
    });
    const updated = await patchResponse.json();

    assert.equal(patchResponse.status, 200);
    assert.equal(updated.status, 'rejected');
    assert.equal(updated.reason, 'needs analyst review');
    assert.ok(updated.responded_at);

    const secondPatch = await fetch(`${baseUrl}/api/approval/${approvalId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'approved' }),
    });

    assert.equal(secondPatch.status, 400);
    assert.deepEqual(await secondPatch.json(), {
      error: 'Only pending approvals can be updated',
    });
  });
});

test('approval detail returns 404 for missing items and rejects invalid statuses', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    const inserted = db.prepare(`
      INSERT INTO approval_queue (trace_id, tool_name, status)
      VALUES ('trace-3', 'block_ip', 'pending')
    `).run();
    const id = Number(inserted.lastInsertRowid);

    const invalid = await fetch(`${baseUrl}/api/approval/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'ignored' }),
    });
    assert.equal(invalid.status, 400);

    const missing = await fetch(`${baseUrl}/api/approval/99999`);
    assert.equal(missing.status, 404);
    assert.deepEqual(await missing.json(), { error: 'Approval not found' });
  });
});

test('audit stats aggregate token usage formats and ignore malformed rows', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    const insert = db.prepare(`
      INSERT INTO audit_logs (trace_id, alert_id, event_type, token_usage, created_at)
      VALUES (?, ?, ?, ?, ?)
    `);
    insert.run('trace-a', '1', 'plan', JSON.stringify({ input_tokens: 10, output_tokens: 5 }), '2026-03-07T10:00:00.000Z');
    insert.run('trace-a', '1', 'execute', JSON.stringify({ prompt_tokens: 3, completion_tokens: 7 }), '2026-03-07T10:05:00.000Z');
    insert.run('trace-b', '2', 'plan', '{bad-json', '2026-03-08T09:00:00.000Z');
    insert.run('trace-b', '2', 'execute', null, '2026-03-08T09:05:00.000Z');

    const response = await fetch(`${baseUrl}/api/audit/stats?days=30`);
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.equal(body.total_analyses, 2);
    assert.equal(body.total_input_tokens, 13);
    assert.equal(body.total_output_tokens, 12);
    assert.equal(body.daily.length, 2);

    const day1 = body.daily.find((row) => row.date === '2026-03-07');
    const day2 = body.daily.find((row) => row.date === '2026-03-08');
    assert.deepEqual(day1, { date: '2026-03-07', analyses: 1, tokens: 25 });
    assert.deepEqual(day2, { date: '2026-03-08', analyses: 1, tokens: 0 });
  });
});

test('audit list honors days filter and validates invalid days', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    const insert = db.prepare(`
      INSERT INTO audit_logs (trace_id, alert_id, event_type, created_at)
      VALUES (?, ?, ?, ?)
    `);
    insert.run('trace-old', '1', 'plan', '2026-02-01T08:00:00.000Z');
    insert.run('trace-new', '2', 'execute', new Date().toISOString());

    const ok = await fetch(`${baseUrl}/api/audit?days=7`);
    const body = await ok.json();
    assert.equal(ok.status, 200);
    assert.equal(body.total, 1);
    assert.equal(body.logs.length, 1);
    assert.equal(body.logs[0].trace_id, 'trace-new');

    const bad = await fetch(`${baseUrl}/api/audit?days=-1`);
    assert.equal(bad.status, 400);
    assert.deepEqual(await bad.json(), { error: 'days must be a non-negative number' });
  });
});

test('audit trace returns ordered logs and summarized token totals', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    const insert = db.prepare(`
      INSERT INTO audit_logs (trace_id, alert_id, event_type, token_usage, created_at)
      VALUES (?, ?, ?, ?, ?)
    `);
    insert.run('trace-z', '7', 'plan', JSON.stringify({ input_tokens: 4, output_tokens: 6 }), '2026-03-08T08:00:00.000Z');
    insert.run('trace-z', '7', 'execute', JSON.stringify({ prompt_tokens: 2, completion_tokens: 3 }), '2026-03-08T08:01:00.000Z');

    const ok = await fetch(`${baseUrl}/api/audit/trace/trace-z`);
    const body = await ok.json();
    assert.equal(ok.status, 200);
    assert.equal(body.trace_id, 'trace-z');
    assert.equal(body.logs.length, 2);
    assert.equal(body.summary.total_steps, 2);
    assert.equal(body.summary.total_tokens, 15);
    assert.equal(body.logs[0].event_type, 'plan');
    assert.equal(body.logs[1].event_type, 'execute');

    const missing = await fetch(`${baseUrl}/api/audit/trace/does-not-exist`);
    assert.equal(missing.status, 404);
    assert.deepEqual(await missing.json(), { error: 'Trace not found' });
  });
});

test('dashboard stats and assets aggregate alerts, decisions, and asset impact', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    db.prepare(`INSERT INTO assets (ip, hostname, type, importance) VALUES ('192.168.0.10', 'HMI-1', 'server', 5)`).run();
    db.prepare(`INSERT INTO assets (ip, hostname, type, importance) VALUES ('192.168.0.20', 'PLC-1', 'host', 4)`).run();

    const insertAlert = db.prepare(`
      INSERT INTO alerts (source, severity, title, status, dst_ip, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    insertAlert.run('waf', 'high', 'SQL Injection', 'open', '192.168.0.10', '2026-03-08T11:00:00.000Z');
    insertAlert.run('nids', 'critical', 'RCE Attempt', 'analyzing', '192.168.0.10', '2026-03-08T11:05:00.000Z');
    insertAlert.run('hids', 'low', 'Config Drift', 'resolved', '192.168.0.20', '2026-03-08T11:10:00.000Z');

    const chainId = Number(db.prepare(`
      INSERT INTO attack_chains (name, stage, confidence, alert_ids, evidence, created_at)
      VALUES ('Chain A', 'Execution', 0.92, '[1,2]', 'matched evidence', '2026-03-08T11:15:00.000Z')
    `).run().lastInsertRowid);

    db.prepare(`
      INSERT INTO decisions (attack_chain_id, risk_level, recommendation, action_type, status)
      VALUES (?, 'high', 'block ip', 'block', 'pending')
    `).run(chainId);

    const statsResp = await fetch(`${baseUrl}/api/dashboard/stats`);
    const stats = await statsResp.json();
    assert.equal(statsResp.status, 200);
    assert.deepEqual(stats.summary, {
      totalAlerts: 3,
      totalChains: 1,
      pendingDecisions: 1,
    });
    assert.equal(stats.alertsByStatus.length, 3);
    assert.equal(stats.alertsBySeverity.length, 3);
    assert.equal(stats.alertsBySource.length, 3);
    assert.equal(stats.recentAlerts.length, 3);
    assert.equal(stats.activeChains.length, 1);
    assert.equal(stats.activeChains[0].decision_status, 'pending');

    const assetsResp = await fetch(`${baseUrl}/api/dashboard/assets`);
    const assets = await assetsResp.json();
    assert.equal(assetsResp.status, 200);
    assert.equal(assets.assets.length, 2);
    assert.equal(assets.assets[0].ip, '192.168.0.10');
    assert.equal(assets.assets[0].alert_count, 2);
    assert.equal(assets.assets[1].alert_count, 1);
  });
});
