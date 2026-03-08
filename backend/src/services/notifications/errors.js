// @ts-check

export class NotificationError extends Error {
  /**
   * @param {string} message
   * @param {{ provider?: string, retryable?: boolean, status?: number, code?: string, cause?: unknown }} [options]
   */
  constructor(message, options = {}) {
    super(message, options.cause ? { cause: options.cause } : undefined);
    this.name = 'NotificationError';
    this.provider = options.provider;
    this.retryable = Boolean(options.retryable);
    this.status = options.status;
    this.code = options.code;
  }
}

/**
 * @param {unknown} error
 * @returns {NotificationError}
 */
export function toNotificationError(error) {
  if (error instanceof NotificationError) {
    return error;
  }
  if (error instanceof Error) {
    return new NotificationError(error.message, { cause: error });
  }
  return new NotificationError(String(error));
}
