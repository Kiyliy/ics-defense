// @ts-check

import { createClient } from 'redis';

const DEFAULT_STREAM_KEY = 'ics:notifications';
const DEFAULT_CONSUMER_GROUP = 'notification-workers';
const DEFAULT_DEAD_LETTER_STREAM_KEY = 'ics:notifications:dead';
const DEFAULT_RETRY_ZSET_KEY = 'ics:notifications:retry';

export function getNotificationQueueConfig({ env = process.env } = {}) {
  return {
    redisUrl: env.REDIS_URL || 'redis://127.0.0.1:6379',
    streamKey: env.NOTIFICATION_STREAM_KEY || DEFAULT_STREAM_KEY,
    consumerGroup: env.NOTIFICATION_CONSUMER_GROUP || DEFAULT_CONSUMER_GROUP,
    deadLetterStreamKey: env.NOTIFICATION_DEAD_LETTER_STREAM_KEY || DEFAULT_DEAD_LETTER_STREAM_KEY,
    retryZsetKey: env.NOTIFICATION_RETRY_ZSET_KEY || DEFAULT_RETRY_ZSET_KEY,
  };
}

export function createRedisConnection({ redisUrl }) {
  const client = createClient({ url: redisUrl });
  client.on('error', () => {});
  return client;
}

function mapRawStreamMessages(raw) {
  if (!Array.isArray(raw)) return [];
  return raw.map(([name, entries]) => ({
    name,
    messages: (entries || []).map(([id, fields]) => {
      const message = {};
      for (let index = 0; index < fields.length; index += 2) {
        message[fields[index]] = fields[index + 1];
      }
      return { id, message };
    }),
  }));
}

export function createNotificationQueue({ client, env = process.env }) {
  const config = getNotificationQueueConfig({ env });

  return {
    config,
    async connect() {
      if (!client.isOpen) await client.connect();
    },
    async disconnect() {
      if (client.isOpen) await client.quit();
    },
    async reconnect() {
      if (client.isOpen) {
        try { await client.quit(); } catch {}
      }
      await client.connect();
    },
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
        await client.xGroupCreate(config.streamKey, config.consumerGroup, '0', { MKSTREAM: true });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (!message.includes('BUSYGROUP')) throw error;
      }
    },
    async read({ consumerName, blockMs = 5000, count = 1 }) {
      await this.connect();
      return client.xReadGroup(config.consumerGroup, consumerName, [{ key: config.streamKey, id: '>' }], { COUNT: count, BLOCK: blockMs });
    },
    async reclaim({ consumerName, minIdleMs = 60000, startId = '0-0', count = 10 }) {
      await this.connect();
      const raw = await client.sendCommand([
        'XAUTOCLAIM',
        config.streamKey,
        config.consumerGroup,
        consumerName,
        String(minIdleMs),
        startId,
        'COUNT',
        String(count),
      ]);
      const [nextId, messages] = raw || ['0-0', []];
      return { nextId, streams: [{ name: config.streamKey, messages: mapRawStreamMessages([[config.streamKey, messages]])[0]?.messages || [] }] };
    },
    async ack(id) {
      await this.connect();
      return client.xAck(config.streamKey, config.consumerGroup, id);
    },
    async addDeadLetter(entry) {
      await this.connect();
      return client.xAdd(config.deadLetterStreamKey, '*', {
        failed_at: new Date().toISOString(),
        source_id: entry.id,
        error: entry.error,
        data: JSON.stringify(entry.payload),
      });
    },
    async scheduleRetry({ payload, dueAt }) {
      await this.connect();
      const key = `${dueAt}:${Math.random().toString(36).slice(2)}`;
      await client.zAdd(config.retryZsetKey, [{ score: dueAt, value: JSON.stringify({ key, payload }) }]);
      return key;
    },
    async moveDueRetries(limit = 20) {
      await this.connect();
      const now = Date.now();
      const dueItems = await client.zRangeByScore(config.retryZsetKey, 0, now, { LIMIT: { offset: 0, count: limit } });
      for (const item of dueItems) {
        const parsed = JSON.parse(item);
        await client.xAdd(config.streamKey, '*', {
          data: JSON.stringify(parsed.payload),
          queued_at: new Date().toISOString(),
          retried_from: config.retryZsetKey,
        });
        await client.zRem(config.retryZsetKey, item);
      }
      return dueItems.length;
    },
  };
}
