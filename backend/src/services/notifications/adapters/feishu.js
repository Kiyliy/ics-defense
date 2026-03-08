// @ts-check

import crypto from 'node:crypto';

/**
 * @typedef {{
 *   provider?: string
 *   title?: string
 *   body?: string
 *   text?: string
 *   msg_type?: 'text' | 'post' | 'interactive'
 *   card?: Record<string, unknown>
 *   metadata?: Record<string, unknown>
 * }} NotificationPayload
 */

/**
 * @typedef {{
 *   msg_type: 'interactive' | 'post' | 'text'
 *   card?: Record<string, unknown>
 *   content?: Record<string, unknown>
 *   timestamp?: string
 *   sign?: string
 * }} FeishuMessageBody
 */

/**
 * @param {string} secret
 * @param {number} timestamp
 */
function genSign(secret, timestamp) {
  const stringToSign = `${timestamp}\n${secret}`;
  return crypto.createHmac('sha256', stringToSign).update('').digest('base64');
}

/**
 * @param {NotificationPayload} payload
 * @returns {FeishuMessageBody}
 */
function buildMessageBody(payload) {
  const msgType = payload.msg_type || (payload.card ? 'interactive' : payload.title ? 'post' : 'text');

  if (msgType === 'interactive') {
    if (!payload.card || typeof payload.card !== 'object') {
      throw new Error('interactive message requires card payload');
    }
    return {
      msg_type: 'interactive',
      card: payload.card,
    };
  }

  if (msgType === 'post') {
    const title = payload.title || 'ICS Defense Notification';
    const contentText = payload.body || payload.text || '';
    return {
      msg_type: 'post',
      content: {
        post: {
          zh_cn: {
            title,
            content: [[{ tag: 'text', text: contentText }]],
          },
        },
      },
    };
  }

  return {
    msg_type: 'text',
    content: {
      text: payload.text || payload.body || payload.title || 'ICS Defense Notification',
    },
  };
}

export class FeishuNotificationAdapter {
  /** @param {{ webhookUrl?: string, secret?: string, fetchFn?: typeof fetch }} options */
  constructor({ webhookUrl, secret, fetchFn = fetch }) {
    this.name = 'feishu';
    this.webhookUrl = webhookUrl;
    this.secret = secret;
    this.fetchFn = fetchFn;
  }

  isEnabled() {
    return Boolean(this.webhookUrl);
  }

  /** @param {NotificationPayload} payload */
  async send(payload) {
    if (!this.webhookUrl) {
      throw new Error('Feishu webhook is not configured');
    }

    const body = buildMessageBody(payload);
    if (this.secret) {
      const timestamp = Math.floor(Date.now() / 1000);
      body.timestamp = String(timestamp);
      body.sign = genSign(this.secret, timestamp);
    }

    const response = await this.fetchFn(this.webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const rawText = await response.text();
    /** @type {any} */
    let data = null;
    if (rawText) {
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { raw: rawText };
      }
    }

    if (!response.ok) {
      throw new Error(`Feishu webhook returned ${response.status}`);
    }

    if (data && typeof data === 'object' && 'code' in data && data.code !== 0) {
      throw new Error(`Feishu webhook failed: ${data.msg || data.code}`);
    }

    return {
      provider: this.name,
      delivered: true,
      request: body,
      response: data,
    };
  }
}
