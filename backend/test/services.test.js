import test from 'node:test';
import assert from 'node:assert/strict';
import { createLLMService } from '../src/services/llm.js';
import { createNotificationService } from '../src/services/notifications/service.js';
import { createNotificationQueue, getNotificationQueueConfig } from '../src/services/notifications/queue.js';
import { FeishuNotificationAdapter } from '../src/services/notifications/adapters/feishu.js';
import { FeishuAppNotificationAdapter } from '../src/services/notifications/adapters/feishu-app.js';
import { NoopNotificationAdapter } from '../src/services/notifications/adapters/noop.js';

function createMockLLMClient(result) {
  return {
    chat: {
      completions: {
        create: async () => result,
      },
    },
  };
}

test('createLLMService parses structured analysis responses and handles fallbacks', async () => {
  const okService = createLLMService({
    client: createMockLLMClient({
      choices: [{ message: { content: JSON.stringify({
        analysis: 'summary',
        mitre_tactic: 'Execution',
        mitre_technique: 'T0807',
        risk_level: 'high',
        confidence: 0.8,
        recommendation: 'block',
        action_type: 'block',
        rationale: 'because',
      }) } }],
    }),
    model: 'test-model',
  });
  const parsed = await okService.analyzeAlerts([{ id: 1 }]);
  assert.equal(parsed.risk_level, 'high');
  assert.equal(parsed.action_type, 'block');

  const invalidJsonService = createLLMService({
    client: createMockLLMClient({ choices: [{ message: { content: 'plain text' } }] }),
  });
  const fallback = await invalidJsonService.analyzeAlerts([{ id: 2 }]);
  assert.equal(fallback.analysis, 'plain text');
  assert.equal(fallback.rationale, 'Failed to parse JSON response');

  const emptyService = createLLMService({
    client: createMockLLMClient({ choices: [{ message: { content: null } }] }),
  });
  const empty = await emptyService.analyzeAlerts([{ id: 3 }]);
  assert.equal(empty.rationale, 'LLM returned empty content');
  assert.equal(empty.action_type, 'manual_review');
});

test('createLLMService chat unwraps content', async () => {
  const service = createLLMService({
    client: createMockLLMClient({ choices: [{ message: { content: 'hello' } }] }),
  });
  assert.equal(await service.chat([{ role: 'user', content: 'ping' }]), 'hello');
});

test('createNotificationService selects providers and forwards payloads', async () => {
  const calls = [];
  const fetchFn = async (url, init) => {
    calls.push({ url, init });
    return { ok: true, text: async () => JSON.stringify({ code: 0, msg: 'ok' }), json: async () => ({ code: 0, msg: 'ok' }) };
  };
  const service = createNotificationService({
    env: {
      NOTIFICATION_PROVIDER: 'feishu',
      FEISHU_BOT_WEBHOOK_URL: 'https://example.com/hook',
      FEISHU_BOT_SECRET: 's3cret',
      FEISHU_APP_ID: 'app-id',
      FEISHU_APP_SECRET: 'app-secret',
      FEISHU_APP_RECEIVE_ID: 'chat123',
      FEISHU_APP_RECEIVE_ID_TYPE: 'chat_id',
    },
    fetchFn,
  });

  const providers = service.listProviders();
  assert.equal(providers.find((item) => item.name === 'feishu')?.is_default, true);
  assert.equal(service.getProvider().name, 'feishu');
  assert.equal(service.getProvider('feishu-app').name, 'feishu-app');
  assert.throws(() => service.getProvider('bad-provider'), /Unsupported notification provider/);

  const delivered = await service.send({ text: 'hello' });
  assert.equal(delivered.provider, 'feishu');
  assert.equal(calls.length, 1);
});

test('notification queue config and queue operations delegate to redis client', async () => {
  const config = getNotificationQueueConfig({ env: { REDIS_URL: 'redis://r', NOTIFICATION_STREAM_KEY: 's', NOTIFICATION_CONSUMER_GROUP: 'g', NOTIFICATION_DEAD_LETTER_STREAM_KEY: 'd' } });
  assert.deepEqual(config, { redisUrl: 'redis://r', streamKey: 's', consumerGroup: 'g', deadLetterStreamKey: 'd' });

  const calls = [];
  const client = {
    isOpen: false,
    connect: async () => { client.isOpen = true; calls.push('connect'); },
    quit: async () => { client.isOpen = false; calls.push('quit'); },
    xAdd: async (...args) => { calls.push(['xAdd', ...args]); return '1-0'; },
    xGroupCreate: async (...args) => { calls.push(['xGroupCreate', ...args]); },
    xReadGroup: async (...args) => { calls.push(['xReadGroup', ...args]); return [{ name: 's', messages: [] }]; },
    xAck: async (...args) => { calls.push(['xAck', ...args]); return 1; },
  };
  const queue = createNotificationQueue({ client, env: { REDIS_URL: 'redis://r', NOTIFICATION_STREAM_KEY: 's', NOTIFICATION_CONSUMER_GROUP: 'g', NOTIFICATION_DEAD_LETTER_STREAM_KEY: 'd' } });
  const enqueued = await queue.enqueue({ text: 'queued' });
  assert.deepEqual(enqueued, { stream_id: '1-0', stream_key: 's' });
  await queue.ensureConsumerGroup();
  assert.deepEqual(await queue.read({ consumerName: 'worker-1', count: 2, blockMs: 1 }), [{ name: 's', messages: [] }]);
  assert.equal(await queue.ack('1-0'), 1);
  assert.equal(await queue.addDeadLetter({ id: '1-0', payload: { text: 'q' }, error: 'boom' }), '1-0');
  await queue.disconnect();
  assert.ok(calls.some((entry) => Array.isArray(entry) && entry[0] === 'xAdd'));

  const busyClient = {
    isOpen: true,
    connect: async () => {},
    quit: async () => {},
    xGroupCreate: async () => { throw new Error('BUSYGROUP Consumer Group name already exists'); },
  };
  const busyQueue = createNotificationQueue({ client: busyClient, env: {} });
  await busyQueue.ensureConsumerGroup();
});

test('feishu adapter builds payloads and handles upstream failures', async () => {
  const adapter = new FeishuNotificationAdapter({
    webhookUrl: 'https://example.com/webhook',
    secret: 'top-secret',
    fetchFn: async (_url, init) => ({ ok: true, text: async () => JSON.stringify({ code: 0, request: JSON.parse(init.body) }) }),
  });
  assert.equal(adapter.isEnabled(), true);
  const sent = await adapter.send({ title: 'T', body: 'B', msg_type: 'post' });
  assert.equal(sent.provider, 'feishu');
  assert.equal(sent.request.msg_type, 'post');
  assert.ok(sent.request.sign);

  await assert.rejects(() => adapter.send({ msg_type: 'interactive' }), /interactive message requires card payload/);
  const badAdapter = new FeishuNotificationAdapter({ webhookUrl: 'https://example.com/webhook', fetchFn: async () => ({ ok: false, status: 500, text: async () => '' }) });
  await assert.rejects(() => badAdapter.send({ text: 'x' }), /returned 500/);
});

test('feishu app adapter gets token, sends messages, and validates config', async () => {
  const fetchCalls = [];
  const adapter = new FeishuAppNotificationAdapter({
    appId: 'app-id',
    appSecret: 'app-secret',
    defaultReceiveId: 'chat-1',
    fetchFn: async (url, init) => {
      fetchCalls.push({ url, init });
      if (String(url).includes('/auth/')) {
        return { ok: true, json: async () => ({ code: 0, tenant_access_token: 'token-123' }) };
      }
      return { ok: true, json: async () => ({ code: 0, data: { message_id: 'm1' } }) };
    },
  });

  assert.equal(adapter.isEnabled(), true);
  const delivered = await adapter.send({ text: 'hello app' });
  assert.equal(delivered.provider, 'feishu-app');
  assert.equal(fetchCalls.length, 2);

  const interactive = await adapter.send({ receive_id: 'chat-2', msg_type: 'interactive', card: { foo: 'bar' } });
  assert.equal(interactive.request.msg_type, 'interactive');

  const unconfigured = new FeishuAppNotificationAdapter({ fetchFn: async () => ({ ok: true, json: async () => ({}) }) });
  assert.equal(unconfigured.isEnabled(), false);
  await assert.rejects(() => unconfigured.getTenantAccessToken(), /credentials are not configured/);
  await assert.rejects(() => unconfigured.send({ text: 'x' }), /receive_id is required/);

  const failingToken = new FeishuAppNotificationAdapter({
    appId: 'app-id',
    appSecret: 'app-secret',
    defaultReceiveId: 'chat-1',
    fetchFn: async () => ({ ok: true, json: async () => ({ code: 1001, msg: 'bad token' }) }),
  });
  await assert.rejects(() => failingToken.send({ text: 'x' }), /Failed to get Feishu tenant_access_token/);
});

test('noop adapter always skips delivery', async () => {
  const adapter = new NoopNotificationAdapter();
  assert.equal(adapter.isEnabled(), true);
  const result = await adapter.send({ text: 'noop' });
  assert.deepEqual(result, {
    provider: 'noop',
    delivered: false,
    skipped: true,
    request: { text: 'noop' },
    response: { message: 'No notification provider configured' },
  });
});
