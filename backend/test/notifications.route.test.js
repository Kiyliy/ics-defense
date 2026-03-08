import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import express from 'express';
import { createNotificationsRouter } from '../src/routes/notifications.js';
import { initDB } from '../src/models/db.js';
import { NotificationError } from '../src/services/notifications/errors.js';

async function withTestServer(run, { queue, notificationService } = {}) {
  const tempDir = mkdtempSync(join(tmpdir(), 'ics-defense-notifications-'));
  const db = initDB(join(tempDir, 'data', 'test.db'));
  const app = express();
  app.use(express.json());
  app.use((req, _res, next) => { req.db = db; next(); });
  app.use('/api/notifications', createNotificationsRouter({ notificationQueue: queue, notificationService }));

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

function fakeNotificationService(overrides = {}) {
  return {
    listProviders: () => [
      { name: 'noop', enabled: true, is_default: false },
      { name: 'feishu', enabled: true, is_default: true },
      { name: 'feishu-app', enabled: false, is_default: false },
    ],
    validatePayload: () => ({ name: 'feishu' }),
    ...overrides,
  };
}

test('GET /api/notifications/providers returns enabled providers', async () => {
  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/notifications/providers`);
    const body = await response.json();
    assert.equal(response.status, 200);
    assert.equal(body.providers.some((provider) => provider.name === 'noop'), true);
    assert.equal(body.providers.some((provider) => provider.name === 'feishu'), true);
    assert.equal(body.providers.some((provider) => provider.name === 'feishu-app'), true);
  }, { notificationService: fakeNotificationService(), queue: { enqueue: async () => ({ stream_id: '0-0', stream_key: 'ics:notifications' }) } });
});

test('POST /api/notifications/test enqueues notification jobs', async () => {
  const queued = [];
  const queue = { enqueue: async (payload) => { queued.push(payload); return { stream_id: '1-0', stream_key: 'ics:notifications' }; } };
  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/notifications/test`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider: 'feishu', text: 'hello feishu' }),
    });
    const body = await response.json();
    assert.equal(response.status, 202);
    assert.equal(body.queued, true);
    assert.equal(body.stream_id, '1-0');
    assert.equal(queued[0].provider, 'feishu');
  }, { queue, notificationService: fakeNotificationService() });
});

test('POST /api/notifications/test rejects unsupported providers before enqueue', async () => {
  let called = false;
  const queue = { enqueue: async () => { called = true; return { stream_id: 'x', stream_key: 'ics:notifications' }; } };
  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/notifications/test`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider: 'ding', text: 'hello' }),
    });
    assert.equal(response.status, 400);
    assert.equal(called, false);
  }, { queue, notificationService: fakeNotificationService({ validatePayload: () => { throw new NotificationError('Unsupported notification provider: ding', { code: 'unsupported_provider' }); } }) });
});

test('POST /api/notifications/test rejects unconfigured provider before enqueue', async () => {
  let called = false;
  const queue = { enqueue: async () => { called = true; return { stream_id: 'x', stream_key: 'ics:notifications' }; } };
  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/notifications/test`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider: 'feishu', text: 'hello' }),
    });
    assert.equal(response.status, 400);
    assert.equal(called, false);
  }, { queue, notificationService: fakeNotificationService({ validatePayload: () => { throw new NotificationError('Notification provider not configured: feishu', { code: 'provider_not_configured' }); } }) });
});

test('POST /api/notifications/test can enqueue feishu-app jobs', async () => {
  const queued = [];
  const queue = { enqueue: async (payload) => { queued.push(payload); return { stream_id: '2-0', stream_key: 'ics:notifications' }; } };
  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/notifications/test`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider: 'feishu-app', text: 'hello app bot', receive_id: 'oc_demo_chat', receive_id_type: 'chat_id' }),
    });
    const body = await response.json();
    assert.equal(response.status, 202);
    assert.equal(body.queued, true);
    assert.equal(queued[0].provider, 'feishu-app');
    assert.equal(queued[0].receive_id, 'oc_demo_chat');
  }, { queue, notificationService: fakeNotificationService({ validatePayload: () => ({ name: 'feishu-app' }) }) });
});

test('POST /api/notifications/alerts/:id/send enqueues alert notifications', async () => {
  const queued = [];
  const queue = { enqueue: async (payload) => { queued.push(payload); return { stream_id: '3-0', stream_key: 'ics:notifications' }; } };
  await withTestServer(async ({ db, baseUrl }) => {
    const inserted = db.prepare(`
      INSERT INTO alerts (source, severity, title, description, src_ip, dst_ip, mitre_tactic, mitre_technique, status)
      VALUES ('waf', 'high', 'SQL Injection', 'payload detected', '10.0.0.1', '10.0.0.2', 'Execution', 'T1059', 'open')
    `).run();
    const response = await fetch(`${baseUrl}/api/notifications/alerts/${inserted.lastInsertRowid}/send`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider: 'feishu' }),
    });
    const body = await response.json();
    assert.equal(response.status, 202);
    assert.equal(body.alert_id, Number(inserted.lastInsertRowid));
    assert.equal(queued[0].msg_type, 'post');
    assert.match(queued[0].body, /等级：high/);
  }, { queue, notificationService: fakeNotificationService() });
});
