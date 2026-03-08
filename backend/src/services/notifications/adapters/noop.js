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
 * }} NotificationPayload
 */

export class NoopNotificationAdapter {
  constructor() {
    this.name = 'noop';
  }

  isEnabled() {
    return true;
  }

  /**
   * @param {NotificationPayload} payload
   */
  async send(payload) {
    return {
      provider: this.name,
      delivered: false,
      skipped: true,
      request: payload,
      response: { message: 'No notification provider configured' },
    };
  }
}
