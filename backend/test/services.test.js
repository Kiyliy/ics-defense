import test from 'node:test';
import assert from 'node:assert/strict';
import { createNotificationService } from '../src/services/notifications/service.js';
import { NotificationError } from '../src/services/notifications/errors.js';
import { computeRetryDelayMs, shouldRetryNotification } from '../src/workers/notification-worker.js';

test('notification service validates unsupported provider', () => {
  const service = createNotificationService({ env: { NOTIFICATION_PROVIDER: 'noop' } });
  assert.throws(() => service.validatePayload({ provider: 'unknown', text: 'hi' }), NotificationError);
});

test('notification service validates configured webhook provider', () => {
  const service = createNotificationService({ env: { NOTIFICATION_PROVIDER: 'feishu', FEISHU_BOT_WEBHOOK_URL: 'https://example.com/hook' } });
  assert.doesNotThrow(() => service.validatePayload({ provider: 'feishu', text: 'hi' }));
});

test('notification service requires receive_id for feishu-app', () => {
  const service = createNotificationService({ env: { FEISHU_APP_ID: 'cli_x', FEISHU_APP_SECRET: 'sec_x' } });
  assert.throws(() => service.validatePayload({ provider: 'feishu-app', text: 'hi' }), NotificationError);
});

test('retry classifier respects structured retryable errors', () => {
  assert.equal(shouldRetryNotification(new NotificationError('rate limit', { retryable: true })), true);
  assert.equal(shouldRetryNotification(new NotificationError('bad request', { retryable: false })), false);
});

test('retry delay grows with attempts', () => {
  const first = computeRetryDelayMs(1);
  const second = computeRetryDelayMs(2);
  assert.equal(first >= 1000, true);
  assert.equal(second >= 2000, true);
});
