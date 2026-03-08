// @ts-check

import { createClient } from 'redis';

const DEFAULT_STREAM_KEY = 'ics:notifications';
const DEFAULT_CONSUMER_GROUP = 'notification-workers';
const DEFAULT_DEAD_LETTER_STREAM_KEY = 'ics:notifications:dead';

/**
 * @param {{ env?: NodeJS.ProcessEnv }} [options]
 */
export function getNotificationQueueConfig({ env = process.env } = {}) {
  return {
    redisUrl: env.REDIS_URL || 'redis://127.0.0.1:6379',
    streamKey: env.NOTIFICATION_STREAM_KEY || DEFAULT_STREAM_KEY,
    consumerGroup: env.NOTIFICATION_CONSUMER_GROUP || DEFAULT_CONSUMER_GROUP,
    deadLetterStreamKey: env.NOTIFICATION_DEAD_LETTER_STREAM_KEY || DEFAULT_DEAD_LETTER_STREAM_KEY,
  };
}

/**
 * @param {{ redisUrl: string }} options
 */
export function createRedisConnection({ redisUrl }) {
  return createClient({ url: redisUrl });
}

/**
 * @param {{ client: any, env?: NodeJS.ProcessEnv }} options
 */
export function createNotificationQueue({ client, env = process.env }) {
  const config = getNotificationQueueConfig({ env });

  return {
    config,
    async connect() {
      if (!client.isOpen) {
        await client.connect();
      }
    },
    async disconnect() {
      if (client.isOpen) {
        await client.quit();
      }
    },
    /**
     * @param {Record<string, unknown>} payload
     */
    async enqueue(payload) {
      await this.connect();
      const streamId = await client.xAdd(config.streamKey, '*', {
        data: JSON.stringify(payload),
        queued_at: new Date().toISOString(),
      });
      return { stream_id: streamId, stream_key: config.streamKey };
    },
    async ensureConsumerGroup() {
      await this.connect();
      try {
        await client.xGroupCreate(config.streamKey, config.consumerGroup, '0', {
          MKSTREAM: true,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (!message.includes('BUSYGROUP')) {
          throw error;
        }
      }
    },
    /**
     * @param {{ consumerName: string, blockMs?: number, count?: number }} options
     */
    async read(options) {
      await this.connect();
      const { consumerName, blockMs = 5000, count = 1 } = options;
      return client.xReadGroup(config.consumerGroup, consumerName, [{
        key: config.streamKey,
        id: '>',
      }], {
        COUNT: count,
        BLOCK: blockMs,
      });
    },
    /**
     * @param {string} id
     */
    async ack(id) {
      await this.connect();
      return client.xAck(config.streamKey, config.consumerGroup, id);
    },
    /**
     * @param {{ id: string, payload: unknown, error: string }} entry
     */
    async addDeadLetter(entry) {
      await this.connect();
      return client.xAdd(config.deadLetterStreamKey, '*', {
        failed_at: new Date().toISOString(),
        source_id: entry.id,
        error: entry.error,
        data: JSON.stringify(entry.payload),
      });
    },
  };
}
