// @ts-check

import { Router } from 'express';
import { createNotificationQueue, createRedisConnection } from '../services/notifications/queue.js';
import { createNotificationService } from '../services/notifications/service.js';

/**
 * @param {any} alert
 * @returns {{ title: string, body: string, msg_type: 'post', metadata: { alert_id: any } }}
 */
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

/**
 * @param {{
 *   notificationQueue?: ReturnType<typeof createNotificationQueue>,
 *   notificationService?: ReturnType<typeof createNotificationService>,
 * }} [options]
 */
export function createNotificationsRouter({
  notificationQueue = createNotificationQueue({
    client: createRedisConnection({ redisUrl: process.env.REDIS_URL || 'redis://127.0.0.1:6379' }),
  }),
  notificationService = createNotificationService(),
} = {}) {
  const router = Router();

  router.get('/providers', (_req, res) => {
    res.json({ providers: notificationService.listProviders() });
  });

  router.post('/test', async (req, res) => {
    const { provider, title, body, text, msg_type, card, receive_id, receive_id_type } = req.body || {};
    if (!text && !body && !title && !card) {
      return res.status(400).json({ error: 'text, body, title or card is required' });
    }

    try {
      const result = await notificationQueue.enqueue({
        provider,
        title,
        body,
        text,
        msg_type,
        card,
        receive_id,
        receive_id_type,
      });
      res.status(202).json({ queued: true, ...result });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  });

  router.post('/alerts/:id/send', async (req, res) => {
    const alert = req.db.prepare('SELECT * FROM alerts WHERE id = ?').get(req.params.id);
    if (!alert) {
      return res.status(404).json({ error: 'Alert not found' });
    }

    try {
      const result = await notificationQueue.enqueue({
        provider: req.body?.provider,
        receive_id: req.body?.receive_id,
        receive_id_type: req.body?.receive_id_type,
        ...buildAlertNotification(alert),
      });
      res.status(202).json({ alert_id: alert.id, queued: true, ...result });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  });

  return router;
}

export default createNotificationsRouter();
