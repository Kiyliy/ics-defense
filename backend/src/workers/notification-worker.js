// @ts-check

import dotenv from 'dotenv';
import { randomInt } from 'node:crypto';
import { createNotificationService } from '../services/notifications/service.js';
import { createNotificationQueue, createRedisConnection } from '../services/notifications/queue.js';

dotenv.config();

const MAX_RETRIES = Number(process.env.NOTIFICATION_MAX_RETRIES || 5);
const BASE_DELAY_MS = Number(process.env.NOTIFICATION_BASE_DELAY_MS || 1000);
const MAX_DELAY_MS = Number(process.env.NOTIFICATION_MAX_DELAY_MS || 30000);
const CONSUMER_NAME = process.env.NOTIFICATION_CONSUMER_NAME || `worker-${process.pid}`;

/**
 * @param {number} ms
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * @param {unknown} error
 */
function isRetryableNotificationError(error) {
  const message = error instanceof Error ? error.message : String(error);
  return /429|frequency_limit_exceeded|timeout|fetch failed|ECONNRESET|ENOTFOUND|5\d\d/i.test(message);
}

/**
 * @param {ReturnType<typeof createNotificationService>} notificationService
 * @param {Record<string, unknown>} payload
 */
async function sendWithRetry(notificationService, payload) {
  let attempt = 0;
  while (attempt <= MAX_RETRIES) {
    try {
      const result = await notificationService.send(payload);
      return { result, attempts: attempt + 1 };
    } catch (error) {
      attempt += 1;
      if (attempt > MAX_RETRIES || !isRetryableNotificationError(error)) {
        throw error;
      }
      const exponentialDelay = Math.min(BASE_DELAY_MS * (2 ** (attempt - 1)), MAX_DELAY_MS);
      const jitter = randomInt(0, Math.max(250, Math.floor(exponentialDelay * 0.2)));
      const waitMs = exponentialDelay + jitter;
      console.warn(`[notification-worker] send failed, retrying in ${waitMs}ms (attempt ${attempt}/${MAX_RETRIES})`, error instanceof Error ? error.message : String(error));
      await sleep(waitMs);
    }
  }
  throw new Error('Notification retry loop exited unexpectedly');
}

async function main() {
  const redis = createRedisConnection({ redisUrl: process.env.REDIS_URL || 'redis://127.0.0.1:6379' });
  const queue = createNotificationQueue({ client: redis });
  const notificationService = createNotificationService();

  await queue.ensureConsumerGroup();
  console.log(`[notification-worker] listening on ${queue.config.streamKey} with group ${queue.config.consumerGroup} as ${CONSUMER_NAME}`);

  for (;;) {
    const streams = await queue.read({ consumerName: CONSUMER_NAME, blockMs: 5000, count: 1 });
    if (!streams || streams.length === 0) {
      continue;
    }

    for (const stream of streams) {
      for (const message of stream.messages) {
        const payload = JSON.parse(message.message.data);
        try {
          const delivery = await sendWithRetry(notificationService, payload);
          console.log(`[notification-worker] delivered ${message.id} via ${delivery.result.provider} after ${delivery.attempts} attempt(s)`);
          await queue.ack(message.id);
        } catch (error) {
          const messageText = error instanceof Error ? error.message : String(error);
          console.error(`[notification-worker] failed ${message.id}: ${messageText}`);
          await queue.addDeadLetter({ id: message.id, payload, error: messageText });
          await queue.ack(message.id);
        }
      }
    }
  }
}

main().catch((error) => {
  console.error('[notification-worker] fatal error', error);
  process.exit(1);
});
