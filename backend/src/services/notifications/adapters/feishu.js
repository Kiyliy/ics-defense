// @ts-check

import crypto from 'node:crypto';
import { NotificationError } from '../errors.js';

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

function genSign(secret, timestamp) {
  const stringToSign = `${timestamp}\n${secret}`;
  return crypto.createHmac('sha256', stringToSign).update('').digest('base64');
}

function buildMessageBody(payload) {
  const msgType = payload.msg_type || (payload.card ? 'interactive' : payload.title ? 'post' : 'text');

  if (msgType === 'interactive') {
    if (!payload.card || typeof payload.card !== 'object') {
      throw new NotificationError('interactive message requires card payload', { provider: 'feishu' });
    }
    return { msg_type: 'interactive', card: payload.card };
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
  constructor({ webhookUrl, secret, fetchFn = fetch }) {
    this.name = 'feishu';
    this.webhookUrl = webhookUrl;
    this.secret = secret;
    this.fetchFn = fetchFn;
  }

  isEnabled() {
    return Boolean(this.webhookUrl);
  }

  async send(payload) {
    if (!this.webhookUrl) {
      throw new NotificationError('Feishu webhook is not configured', { provider: this.name });
    }

    const body = buildMessageBody(payload);
    if (this.secret) {
      const timestamp = Math.floor(Date.now() / 1000);
      body.timestamp = String(timestamp);
      body.sign = genSign(this.secret, timestamp);
    }

    let response;
    try {
      response = await this.fetchFn(this.webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (error) {
      throw new NotificationError(`Feishu webhook request failed: ${error instanceof Error ? error.message : String(error)}`, {
        provider: this.name,
        retryable: true,
        cause: error,
      });
    }

    const rawText = await response.text();
    let data = null;
    if (rawText) {
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { raw: rawText };
      }
    }

    if (!response.ok) {
      throw new NotificationError(`Feishu webhook returned ${response.status}`, {
        provider: this.name,
        status: response.status,
        retryable: response.status === 429 || response.status >= 500,
      });
    }

    if (data && typeof data === 'object' && 'code' in data && data.code !== 0) {
      const code = String(data.code);
      const message = String(data.msg || data.code);
      throw new NotificationError(`Feishu webhook failed: ${message}`, {
        provider: this.name,
        code,
        retryable: /frequency_limit_exceeded/i.test(message) || code === '429',
      });
    }

    return {
      provider: this.name,
      delivered: true,
      request: body,
      response: data,
    };
  }
}
