// @ts-check

import { Router } from 'express';
import { createNotificationQueue, createRedisConnection } from '../services/notifications/queue.js';
import { createNotificationService } from '../services/notifications/service.js';
import { NotificationError } from '../services/notifications/errors.js';

function buildAlertNotification(alert) {
  return {
    title: `告警通知：${alert.title}`,
    body: [
      `来源：${alert.source}`,
      `等级：${alert.severity}`,
      `状态：${alert.status}`,
      alert.src_ip ? `源IP：${alert.src_ip}` : null,
      alert.dst_ip ? `目标IP：${alert.dst_ip}` : null,
      alert.mitre_tactic ? `战术：${alert.mitre_tactic}` : null,
      alert.mitre_technique ? `技术：${alert.mitre_technique}` : null,
      alert.description ? `描述：${alert.description}` : null,
      `告警ID：${alert.id}`,
    ].filter(Boolean).join('\n'),
    msg_type: 'post',
    metadata: { alert_id: alert.id },
  };
}

function getStatusCode(error) {
  if (error instanceof NotificationError) {
    if (error.code === 'unsupported_provider') return 400;
    if (error.code === 'provider_not_configured' || error.code === 'missing_receive_id') return 400;
  }
  return 500;
}

export function createNotificationsRouter({
  notificationQueue = createNotificationQueue({ client: createRedisConnection({ redisUrl: process.env.REDIS_URL || 'redis://127.0.0.1:6379' }) }),
  notificationService = createNotificationService(),
} = {}) {
  const router = Router();

  router.get('/providers', (_req, res) => {
    res.json({ providers: notificationService.listProviders() });
  });

  router.post('/test', async (req, res) => {
    const payload = (({ provider, title, body, text, msg_type, card, receive_id, receive_id_type }) => ({ provider, title, body, text, msg_type, card, receive_id, receive_id_type }))(req.body || {});
    if (!payload.text && !payload.body && !payload.title && !payload.card) {
      return res.status(400).json({ error: 'text, body, title or card is required' });
    }

    try {
      notificationService.validatePayload(payload);
      const result = await notificationQueue.enqueue(payload);
      res.status(202).json({ queued: true, ...result });
    } catch (error) {
      res.status(getStatusCode(error)).json({ error: error instanceof Error ? error.message : String(error) });
    }
  });

  router.post('/alerts/:id/send', async (req, res) => {
    const alert = req.db.prepare('SELECT * FROM alerts WHERE id = ?').get(req.params.id);
    if (!alert) {
      return res.status(404).json({ error: 'Alert not found' });
    }

    const payload = {
      provider: req.body?.provider,
      receive_id: req.body?.receive_id,
      receive_id_type: req.body?.receive_id_type,
      ...buildAlertNotification(alert),
    };

    try {
      notificationService.validatePayload(payload);
      const result = await notificationQueue.enqueue(payload);
      res.status(202).json({ alert_id: alert.id, queued: true, ...result });
    } catch (error) {
      res.status(getStatusCode(error)).json({ error: error instanceof Error ? error.message : String(error) });
    }
  });

  return router;
}

export default createNotificationsRouter();
