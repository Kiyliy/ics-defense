import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import express from 'express';
import { createNotificationsRouter } from '../src/routes/notifications.js';
import { createNotificationService } from '../src/services/notifications/service.js';
import { initDB } from '../src/models/db.js';

async function withTestServer(run, { env = {}, fetchFn } = {}) {
  const tempDir = mkdtempSync(join(tmpdir(), 'ics-defense-notifications-'));
  const db = initDB(join(tempDir, 'data', 'test.db'));
  const app = express();
  app.use(express.json());
  app.use((req, _res, next) => {
    req.db = db;
    next();
  });

  const notificationService = createNotificationService({
    env: { ...process.env, ...env },
    fetchFn,
  });
  app.use('/api/notifications', createNotificationsRouter({ notificationService }));

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

test('GET /api/notifications/providers returns enabled providers', async () => {
  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/notifications/providers`);
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.equal(body.providers.some((provider) => provider.name === 'noop'), true);
    assert.equal(body.providers.some((provider) => provider.name === 'feishu'), true);
    assert.equal(body.providers.some((provider) => provider.name === 'feishu-app'), true);
  });
});

test('POST /api/notifications/test sends text through Feishu adapter', async () => {
  const requests = [];
  const fetchFn = async (url, options) => {
    requests.push({ url, options });
    return new Response(JSON.stringify({ code: 0, msg: 'success', data: {} }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/notifications/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: 'feishu',
        text: 'hello feishu',
      }),
    });
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.equal(body.provider, 'feishu');
    assert.equal(body.delivered, true);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, 'https://example.com/webhook');

    const payload = JSON.parse(requests[0].options.body);
    assert.equal(payload.msg_type, 'text');
    assert.equal(payload.content.text, 'hello feishu');
  }, {
    env: {
      FEISHU_BOT_WEBHOOK_URL: 'https://example.com/webhook',
      FEISHU_BOT_SECRET: 'demo-secret',
      NOTIFICATION_PROVIDER: 'feishu',
    },
    fetchFn,
  });
});



test('POST /api/notifications/test sends text through Feishu app bot adapter', async () => {
  const requests = [];
  const fetchFn = async (url, options) => {
    requests.push({ url, options });
    if (String(url).includes('/auth/v3/tenant_access_token/internal')) {
      return new Response(JSON.stringify({ code: 0, msg: 'ok', tenant_access_token: 't-demo', expire: 7200 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ code: 0, msg: 'success', data: { message_id: 'om_demo' } }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  await withTestServer(async ({ baseUrl }) => {
    const response = await fetch(`${baseUrl}/api/notifications/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: 'feishu-app',
        text: 'hello app bot',
      }),
    });
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.equal(body.provider, 'feishu-app');
    assert.equal(body.delivered, true);
    assert.equal(requests.length, 2);
    assert.match(String(requests[0].url), /tenant_access_token\/internal/);
    assert.match(String(requests[1].url), /im\/v1\/messages\?receive_id_type=chat_id/);

    const tokenPayload = JSON.parse(requests[0].options.body);
    assert.equal(tokenPayload.app_id, 'cli_demo');
    assert.equal(tokenPayload.app_secret, 'secret_demo');

    const msgPayload = JSON.parse(requests[1].options.body);
    assert.equal(msgPayload.receive_id, 'oc_demo_chat');
    assert.equal(msgPayload.msg_type, 'text');
    assert.equal(JSON.parse(msgPayload.content).text, 'hello app bot');
    assert.equal(requests[1].options.headers.Authorization, 'Bearer t-demo');
  }, {
    env: {
      FEISHU_APP_ID: 'cli_demo',
      FEISHU_APP_SECRET: 'secret_demo',
      FEISHU_APP_RECEIVE_ID: 'oc_demo_chat',
      FEISHU_APP_RECEIVE_ID_TYPE: 'chat_id',
      NOTIFICATION_PROVIDER: 'feishu-app',
    },
    fetchFn,
  });
});

test('POST /api/notifications/alerts/:id/send formats alert content', async () => {
  const fetchFn = async (_url, options) => new Response(JSON.stringify({
    code: 0,
    msg: 'success',
    echoed: JSON.parse(options.body),
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

  await withTestServer(async ({ db, baseUrl }) => {
    const inserted = db.prepare(`
      INSERT INTO alerts (source, severity, title, description, src_ip, dst_ip, mitre_tactic, mitre_technique, status)
      VALUES ('waf', 'high', 'SQL Injection', 'payload detected', '10.0.0.1', '10.0.0.2', 'Execution', 'T1059', 'open')
    `).run();

    const response = await fetch(`${baseUrl}/api/notifications/alerts/${inserted.lastInsertRowid}/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: 'feishu' }),
    });
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.equal(body.provider, 'feishu');
    assert.equal(body.alert_id, Number(inserted.lastInsertRowid));
    assert.equal(body.request.msg_type, 'post');
    assert.equal(body.request.content.post.zh_cn.title, '告警通知：SQL Injection');
    assert.match(body.request.content.post.zh_cn.content[0][0].text, /等级：high/);
  }, {
    env: {
      FEISHU_BOT_WEBHOOK_URL: 'https://example.com/webhook',
      NOTIFICATION_PROVIDER: 'feishu',
    },
    fetchFn,
  });
});
