// @ts-check

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

/**
 * @param {NotificationPayload} payload
 */
function buildMessageContent(payload) {
  const msgType = payload.msg_type || (payload.card ? 'interactive' : payload.title ? 'post' : 'text');

  if (msgType === 'interactive') {
    if (!payload.card || typeof payload.card !== 'object') {
      throw new Error('interactive message requires card payload');
    }
    return {
      msg_type: 'interactive',
      content: JSON.stringify(payload.card),
    };
  }

  if (msgType === 'post') {
    const title = payload.title || 'ICS Defense Notification';
    const contentText = payload.body || payload.text || '';
    return {
      msg_type: 'post',
      content: JSON.stringify({
        zh_cn: {
          title,
          content: [[{ tag: 'text', text: contentText }]],
        },
      }),
    };
  }

  return {
    msg_type: 'text',
    content: JSON.stringify({
      text: payload.text || payload.body || payload.title || 'ICS Defense Notification',
    }),
  };
}

export class FeishuAppNotificationAdapter {
  /**
   * @param {{
   *   appId?: string,
   *   appSecret?: string,
   *   defaultReceiveId?: string,
   *   defaultReceiveIdType?: NotificationPayload['receive_id_type'],
   *   fetchFn?: typeof fetch,
   *   baseUrl?: string,
   * }} options
   */
  constructor({
    appId,
    appSecret,
    defaultReceiveId,
    defaultReceiveIdType = 'chat_id',
    fetchFn = fetch,
    baseUrl = 'https://open.feishu.cn/open-apis',
  }) {
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
      throw new Error('Feishu app credentials are not configured');
    }

    const response = await this.fetchFn(`${this.baseUrl}/auth/v3/tenant_access_token/internal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        app_id: this.appId,
        app_secret: this.appSecret,
      }),
    });

    const data = await response.json();
    if (!response.ok || data.code !== 0 || !data.tenant_access_token) {
      throw new Error(`Failed to get Feishu tenant_access_token: ${data.msg || response.status}`);
    }

    return data.tenant_access_token;
  }

  /**
   * @param {NotificationPayload} payload
   */
  async send(payload) {
    const receiveId = payload.receive_id || this.defaultReceiveId;
    const receiveIdType = payload.receive_id_type || this.defaultReceiveIdType;
    if (!receiveId) {
      throw new Error('receive_id is required for feishu-app notifications');
    }

    const accessToken = await this.getTenantAccessToken();
    const message = buildMessageContent(payload);
    const response = await this.fetchFn(
      `${this.baseUrl}/im/v1/messages?receive_id_type=${encodeURIComponent(receiveIdType)}`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json; charset=utf-8',
        },
        body: JSON.stringify({
          receive_id: receiveId,
          ...message,
        }),
      }
    );

    const data = await response.json();
    if (!response.ok || data.code !== 0) {
      throw new Error(`Feishu app bot failed: ${data.msg || response.status}`);
    }

    return {
      provider: this.name,
      delivered: true,
      request: {
        receive_id: receiveId,
        receive_id_type: receiveIdType,
        ...message,
      },
      response: data,
    };
  }
}
