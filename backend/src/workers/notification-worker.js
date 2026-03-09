// @ts-check

import dotenv from 'dotenv';
import { randomInt } from 'node:crypto';
import { createNotificationService } from '../services/notifications/service.js';
import { createNotificationQueue, createRedisConnection } from '../services/notifications/queue.js';
import { NotificationError, toNotificationError } from '../services/notifications/errors.js';

dotenv.config();

const MAX_RETRIES = Number(process.env.NOTIFICATION_MAX_RETRIES || 5);
const BASE_DELAY_MS = Number(process.env.NOTIFICATION_BASE_DELAY_MS || 1000);
const MAX_DELAY_MS = Number(process.env.NOTIFICATION_MAX_DELAY_MS || 30000);
const CONSUMER_NAME = process.env.NOTIFICATION_CONSUMER_NAME || `worker-${process.pid}`;
const RECLAIM_MIN_IDLE_MS = Number(process.env.NOTIFICATION_RECLAIM_MIN_IDLE_MS || 60000);

export function computeRetryDelayMs(attempt) {
  const exponentialDelay = Math.min(BASE_DELAY_MS * (2 ** Math.max(0, attempt - 1)), MAX_DELAY_MS);
  const jitter = randomInt(0, Math.max(250, Math.floor(exponentialDelay * 0.2)));
  return exponentialDelay + jitter;
}

export function shouldRetryNotification(error) {
  const normalized = toNotificationError(error);
  if (normalized.retryable) return true;
  return /429|frequency_limit_exceeded|timeout|fetch failed|ECONNRESET|ENOTFOUND|5\d\d/i.test(normalized.message);
}

export async function processMessage({ queue, notificationService, message }) {
  const payload = JSON.parse(message.message.data);
  const attempt = Number(payload.attempt || 0);

  try {
    const delivery = await notificationService.send(payload);
    console.log(`[notification-worker] delivered ${message.id} via ${delivery.provider} after ${attempt + 1} attempt(s)`);
    await queue.ack(message.id);
    return { status: 'delivered' };
  } catch (error) {
    const notificationError = toNotificationError(error);
    if (attempt < MAX_RETRIES && shouldRetryNotification(notificationError)) {
      const nextAttempt = attempt + 1;
      const delayMs = computeRetryDelayMs(nextAttempt);
      await queue.scheduleRetry({
        payload: {
          ...payload,
          attempt: nextAttempt,
          last_error: notificationError.message,
          next_attempt_at: new Date(Date.now() + delayMs).toISOString(),
        },
        dueAt: Date.now() + delayMs,
      });
      await queue.ack(message.id);
      console.warn(`[notification-worker] scheduled retry for ${message.id} in ${delayMs}ms (attempt ${nextAttempt}/${MAX_RETRIES})`);
      return { status: 'retried' };
    }

    try {
      await queue.addDeadLetter({ id: message.id, payload: { ...payload, last_error: notificationError.message }, error: notificationError.message });
      await queue.ack(message.id);
    } catch (deadLetterError) {
      console.error('[notification-worker] dead-letter write failed', deadLetterError);
      throw deadLetterError;
    }

    console.error(`[notification-worker] failed ${message.id}: ${notificationError.message}`);
    return { status: 'dead-lettered' };
  }
}

async function main() {
  const redis = createRedisConnection({ redisUrl: process.env.REDIS_URL || 'redis://127.0.0.1:6379' });
  const queue = createNotificationQueue({ client: redis });
  const notificationService = createNotificationService();
  let reclaimCursor = '0-0';

  await queue.ensureConsumerGroup();
  console.log(`[notification-worker] listening on ${queue.config.streamKey} with group ${queue.config.consumerGroup} as ${CONSUMER_NAME}`);

  for (;;) {
    try {
      await queue.moveDueRetries();

      const reclaimed = await queue.reclaim({ consumerName: CONSUMER_NAME, minIdleMs: RECLAIM_MIN_IDLE_MS, startId: reclaimCursor, count: 10 });
      reclaimCursor = reclaimed.nextId || '0-0';
      for (const stream of reclaimed.streams || []) {
        for (const message of stream.messages || []) {
          await processMessage({ queue, notificationService, message });
        }
      }

      const streams = await queue.read({ consumerName: CONSUMER_NAME, blockMs: 5000, count: 5 });
      if (!streams || streams.length === 0) continue;

      for (const stream of streams) {
        for (const message of stream.messages) {
          await processMessage({ queue, notificationService, message });
        }
      }
    } catch (error) {
      console.error('[notification-worker] loop error', error);
      try {
        await queue.reconnect();
        await queue.ensureConsumerGroup();
      } catch (reconnectError) {
        console.error('[notification-worker] reconnect failed', reconnectError);
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  }
}

main().catch((error) => {
  console.error('[notification-worker] fatal error', error);
  process.exit(1);
});
