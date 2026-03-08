import { describe, it, expect } from 'vitest';
import { createNotificationService } from '../src/services/notifications/service.js';
import { NotificationError } from '../src/services/notifications/errors.js';
import { computeRetryDelayMs, shouldRetryNotification } from '../src/workers/notification-worker.js';

describe('notification services', () => {
  it('notification service validates unsupported provider', () => {
    const service = createNotificationService({ env: { NOTIFICATION_PROVIDER: 'noop' } });
    expect(() => service.validatePayload({ provider: 'unknown', text: 'hi' })).toThrow(NotificationError);
  });

  it('notification service validates configured webhook provider', () => {
    const service = createNotificationService({ env: { NOTIFICATION_PROVIDER: 'feishu', FEISHU_BOT_WEBHOOK_URL: 'https://example.com/hook' } });
    expect(() => service.validatePayload({ provider: 'feishu', text: 'hi' })).not.toThrow();
  });

  it('notification service requires receive_id for feishu-app', () => {
    const service = createNotificationService({ env: { FEISHU_APP_ID: 'cli_x', FEISHU_APP_SECRET: 'sec_x' } });
    expect(() => service.validatePayload({ provider: 'feishu-app', text: 'hi' })).toThrow(NotificationError);
  });

  it('retry classifier respects structured retryable errors', () => {
    expect(shouldRetryNotification(new NotificationError('rate limit', { retryable: true }))).toBe(true);
    expect(shouldRetryNotification(new NotificationError('bad request', { retryable: false }))).toBe(false);
  });

  it('retry delay grows with attempts', () => {
    const first = computeRetryDelayMs(1);
    const second = computeRetryDelayMs(2);
    expect(first >= 1000).toBe(true);
    expect(second >= 2000).toBe(true);
  });
});
