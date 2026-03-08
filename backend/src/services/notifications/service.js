// @ts-check

import { FeishuNotificationAdapter } from './adapters/feishu.js';
import { FeishuAppNotificationAdapter } from './adapters/feishu-app.js';
import { NoopNotificationAdapter } from './adapters/noop.js';
import { NotificationError } from './errors.js';

/** @typedef {'noop' | 'feishu' | 'feishu-app'} ProviderName */

export function createNotificationService({ env = process.env, fetchFn = fetch } = {}) {
  const adapters = {
    noop: new NoopNotificationAdapter(),
    feishu: new FeishuNotificationAdapter({ webhookUrl: env.FEISHU_BOT_WEBHOOK_URL, secret: env.FEISHU_BOT_SECRET, fetchFn }),
    'feishu-app': new FeishuAppNotificationAdapter({
      appId: env.FEISHU_APP_ID,
      appSecret: env.FEISHU_APP_SECRET,
      defaultReceiveId: env.FEISHU_APP_RECEIVE_ID,
      defaultReceiveIdType: /** @type {any} */ (env.FEISHU_APP_RECEIVE_ID_TYPE || 'chat_id'),
      fetchFn,
    }),
  };

  const defaultProvider = env.NOTIFICATION_PROVIDER
    || (adapters['feishu-app'].isEnabled() ? 'feishu-app' : adapters.feishu.isEnabled() ? 'feishu' : 'noop');

  return {
    listProviders() {
      return Object.values(adapters).map((adapter) => ({ name: adapter.name, enabled: adapter.isEnabled(), is_default: adapter.name === defaultProvider }));
    },
    getProvider(name) {
      const providerName = /** @type {ProviderName} */ (name || defaultProvider);
      const adapter = adapters[providerName];
      if (!adapter) {
        throw new NotificationError(`Unsupported notification provider: ${providerName}`, { code: 'unsupported_provider' });
      }
      return adapter;
    },
    validatePayload(payload = {}) {
      const adapter = this.getProvider(payload.provider);
      if (adapter.name !== 'noop' && !adapter.isEnabled()) {
        throw new NotificationError(`Notification provider not configured: ${adapter.name}`, { provider: adapter.name, code: 'provider_not_configured' });
      }
      if (adapter.name === 'feishu-app' && !(payload.receive_id || env.FEISHU_APP_RECEIVE_ID)) {
        throw new NotificationError('receive_id is required for feishu-app notifications', { provider: adapter.name, code: 'missing_receive_id' });
      }
      return adapter;
    },
    async send(payload) {
      const adapter = this.validatePayload(payload);
      return adapter.send(payload);
    },
  };
}
