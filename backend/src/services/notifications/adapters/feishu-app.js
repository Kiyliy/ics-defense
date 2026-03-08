// @ts-check

import { NotificationError } from '../errors.js';

function buildMessageContent(payload) {
  const msgType = payload.msg_type || (payload.card ? 'interactive' : payload.title ? 'post' : 'text');

  if (msgType === 'interactive') {
    if (!payload.card || typeof payload.card !== 'object') {
      throw new NotificationError('interactive message requires card payload', { provider: 'feishu-app' });
    }
    return { msg_type: 'interactive', content: JSON.stringify(payload.card) };
  }

  if (msgType === 'post') {
    const title = payload.title || 'ICS Defense Notification';
    const contentText = payload.body || payload.text || '';
    return {
      msg_type: 'post',
      content: JSON.stringify({
        zh_cn: { title, content: [[{ tag: 'text', text: contentText }]] },
      }),
    };
  }

  return {
    msg_type: 'text',
    content: JSON.stringify({ text: payload.text || payload.body || payload.title || 'ICS Defense Notification' }),
  };
}

export class FeishuAppNotificationAdapter {
  constructor({ appId, appSecret, defaultReceiveId, defaultReceiveIdType = 'chat_id', fetchFn = fetch, baseUrl = 'https://open.feishu.cn/open-apis' }) {
    this.name = 'feishu-app';
    this.appId = appId;
    this.appSecret = appSecret;
    this.defaultReceiveId = defaultReceiveId;
    this.defaultReceiveIdType = defaultReceiveIdType;
    this.fetchFn = fetchFn;
    this.baseUrl = baseUrl;
  }

  isEnabled() {
    return Boolean(this.appId && this.appSecret);
  }

  async getTenantAccessToken() {
    if (!this.appId || !this.appSecret) {
      throw new NotificationError('Feishu app credentials are not configured', { provider: this.name });
    }

    let response;
    try {
      response = await this.fetchFn(`${this.baseUrl}/auth/v3/tenant_access_token/internal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ app_id: this.appId, app_secret: this.appSecret }),
      });
    } catch (error) {
      throw new NotificationError(`Feishu app token request failed: ${error instanceof Error ? error.message : String(error)}`, {
        provider: this.name,
        retryable: true,
        cause: error,
      });
    }

    const data = await response.json();
    if (!response.ok || data.code !== 0 || !data.tenant_access_token) {
      throw new NotificationError(`Failed to get Feishu tenant_access_token: ${data.msg || response.status}`, {
        provider: this.name,
        status: response.status,
        code: data?.code ? String(data.code) : undefined,
        retryable: response.status === 429 || response.status >= 500,
      });
    }

    return data.tenant_access_token;
  }

  async send(payload) {
    const receiveId = payload.receive_id || this.defaultReceiveId;
    const receiveIdType = payload.receive_id_type || this.defaultReceiveIdType;
    if (!receiveId) {
      throw new NotificationError('receive_id is required for feishu-app notifications', { provider: this.name });
    }

    const accessToken = await this.getTenantAccessToken();
    const message = buildMessageContent(payload);

    let response;
    try {
      response = await this.fetchFn(`${this.baseUrl}/im/v1/messages?receive_id_type=${encodeURIComponent(receiveIdType)}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json; charset=utf-8',
        },
        body: JSON.stringify({ receive_id: receiveId, ...message }),
      });
    } catch (error) {
      throw new NotificationError(`Feishu app bot request failed: ${error instanceof Error ? error.message : String(error)}`, {
        provider: this.name,
        retryable: true,
        cause: error,
      });
    }

    const data = await response.json();
    if (!response.ok || data.code !== 0) {
      throw new NotificationError(`Feishu app bot failed: ${data.msg || response.status}`, {
        provider: this.name,
        status: response.status,
        code: data?.code ? String(data.code) : undefined,
        retryable: response.status === 429 || response.status >= 500,
      });
    }

    return {
      provider: this.name,
      delivered: true,
      request: { receive_id: receiveId, receive_id_type: receiveIdType, ...message },
      response: data,
    };
  }
}
