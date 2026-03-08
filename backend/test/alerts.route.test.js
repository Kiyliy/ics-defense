import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import express from 'express';
import alertsRouter from '../src/routes/alerts.js';
import { initDB } from '../src/models/db.js';

async function withTestServer(run) {
  const tempDir = mkdtempSync(join(tmpdir(), 'ics-defense-alerts-'));
  const db = initDB(join(tempDir, 'data', 'test.db'));
  const app = express();
  app.use(express.json());
  app.use((req, _res, next) => {
    req.db = db;
    next();
  });
  app.use('/api/alerts', alertsRouter);

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

test('POST /api/alerts/ingest rejects invalid payloads', async () => {
  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/alerts/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: 'waf' }),
    });

    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: 'source and events[] required' });
  });
});

test('POST /api/alerts/ingest stores raw and normalized alerts', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/alerts/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: 'waf',
        events: [
          {
            risk_level: 'high',
            event_type: 'XSS attack attempt',
            detail: 'reflected payload',
            remote_addr: '10.10.10.1',
            server_addr: '10.10.10.2',
          },
        ],
      }),
    });

    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.ingested, 1);
    assert.equal(body.alerts[0].severity, 'high');
    assert.equal(body.alerts[0].mitre_tactic, 'Execution');
    assert.equal(body.alerts[0].src_ip, '10.10.10.1');
    assert.equal(body.alerts[0].dst_ip, '10.10.10.2');

    const rawCount = db.prepare('SELECT COUNT(*) AS count FROM raw_events').get();
    const alert = db.prepare('SELECT * FROM alerts').get();

    assert.equal(rawCount.count, 1);
    assert.equal(alert.source, 'waf');
    assert.equal(alert.title, 'XSS attack attempt');
    assert.equal(alert.status, 'open');
  });
});

test('GET /api/alerts applies filters and pagination', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    const insert = db.prepare(`
      INSERT INTO alerts (source, severity, title, description, status)
      VALUES (?, ?, ?, ?, ?)
    `);
    insert.run('waf', 'high', 'A1', 'first', 'open');
    insert.run('waf', 'low', 'A2', 'second', 'resolved');
    insert.run('nids', 'high', 'A3', 'third', 'open');

    const response = await fetch(`${baseUrl}/api/alerts?severity=high&status=open&limit=1&offset=0`);
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.equal(body.total, 2);
    assert.equal(body.alerts.length, 1);
    assert.equal(body.alerts[0].severity, 'high');
    assert.equal(body.alerts[0].status, 'open');

    const invalid = await fetch(`${baseUrl}/api/alerts?limit=-1&offset=0`);
    assert.equal(invalid.status, 400);
    assert.deepEqual(await invalid.json(), { error: 'limit must be a non-negative integer' });
  });
});

test('PATCH /api/alerts/:id/status validates status, updates alert, and returns 404 for missing alert', async () => {
  await withTestServer(async ({ db, baseUrl }) => {
    const inserted = db.prepare(`
      INSERT INTO alerts (source, severity, title, status)
      VALUES ('waf', 'medium', 'Needs review', 'open')
    `).run();
    const id = Number(inserted.lastInsertRowid);

    const badResponse = await fetch(`${baseUrl}/api/alerts/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'closed' }),
    });
    assert.equal(badResponse.status, 400);

    const missingResponse = await fetch(`${baseUrl}/api/alerts/999/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'resolved' }),
    });
    assert.equal(missingResponse.status, 404);
    assert.deepEqual(await missingResponse.json(), { error: 'Alert not found' });

    const okResponse = await fetch(`${baseUrl}/api/alerts/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'resolved' }),
    });
    assert.equal(okResponse.status, 200);
    assert.deepEqual(await okResponse.json(), { updated: true });

    const alert = db.prepare('SELECT status FROM alerts WHERE id = ?').get(id);
    assert.equal(alert.status, 'resolved');
  });
});
