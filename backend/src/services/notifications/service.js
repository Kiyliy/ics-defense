// @ts-check

import { FeishuNotificationAdapter } from './adapters/feishu.js';
import { FeishuAppNotificationAdapter } from './adapters/feishu-app.js';
import { NoopNotificationAdapter } from './adapters/noop.js';

/**
 * @typedef {{
 *   provider?: string
 *   title?: string
 *   body?: string
 *   text?: string
 *   msg_type?: 'text' | 'post' | 'interactive'
 *   card?: Record<string, unknown>
 *   metadata?: Record<string, unknown>
 *   receive_id?: string
 *   receive_id_type?: 'chat_id' | 'open_id' | 'user_id' | 'union_id' | 'email'
 * }} NotificationPayload
 */

/** @typedef {'noop' | 'feishu' | 'feishu-app'} ProviderName */

/**
 * @param {{ env?: NodeJS.ProcessEnv, fetchFn?: typeof fetch }} [options]
 */
export function createNotificationService({ env = process.env, fetchFn = fetch } = {}) {
  const adapters = {
    noop: new NoopNotificationAdapter(),
    feishu: new FeishuNotificationAdapter({
      webhookUrl: env.FEISHU_BOT_WEBHOOK_URL,
      secret: env.FEISHU_BOT_SECRET,
      fetchFn,
    }),
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
      return Object.values(adapters).map((adapter) => ({
        name: adapter.name,
        enabled: adapter.isEnabled(),
        is_default: adapter.name === defaultProvider,
      }));
    },
    /** @param {string | undefined} name */
    getProvider(name) {
      const providerName = /** @type {ProviderName} */ (name || defaultProvider);
      const adapter = adapters[providerName];
      if (!adapter) {
        throw new Error(`Unsupported notification provider: ${providerName}`);
      }
      return adapter;
    },
    /** @param {NotificationPayload} payload */
    async send(payload) {
      const adapter = this.getProvider(payload.provider);
      return adapter.send(payload);
    },
  };
}
