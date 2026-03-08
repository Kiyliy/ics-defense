/**
 * @typedef {{ date?: string, hour?: string, count?: number }} TrendPoint
 * @typedef {{ trace_id?: string, created_at?: string }} AuditLog
 */

/**
 * @param {TrendPoint[]} trend
 * @returns {{ labels: string[], counts: number[] }}
 */
export function buildTrendSeries(trend = []) {
  return {
    labels: trend.map((item) => item.date || item.hour || ''),
    counts: trend.map((item) => item.count || 0),
  }
}

/**
 * @param {unknown} raw
 * @returns {number[]}
 */
function parseAlertIds(raw) {
  if (Array.isArray(raw)) return raw.map(Number).filter(Number.isFinite)
  if (typeof raw !== 'string' || !raw.trim()) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.map(Number).filter(Number.isFinite) : []
  } catch {
    return []
  }
}

/**
 * @param {Record<string, any>} chain
 */
export function normalizeAttackChain(chain) {
  const alerts = Array.isArray(chain?.alerts) ? chain.alerts : []
  const decisions = Array.isArray(chain?.decisions)
    ? chain.decisions
    : (chain?.recommendation || chain?.action_type || chain?.decision_status
        ? [{
            id: chain.decision_id || chain.id,
            recommendation: chain.recommendation || '',
            action_type: chain.action_type || '',
            status: chain.decision_status || chain.status || 'pending',
            risk_level: chain.risk_level || 'unknown',
          }]
        : [])

  const alertIds = parseAlertIds(chain?.alert_ids)
  const derivedStatus = chain?.status || chain?.decision_status || (decisions[0]?.status ?? 'pending')

  return {
    ...chain,
    alerts,
    decisions,
    alert_count: Number(chain?.alert_count ?? alerts.length ?? alertIds.length) || alertIds.length,
    status: derivedStatus,
  }
}

/**
 * @param {AuditLog[]} logs
 * @param {number} days
 * @returns {AuditLog[]}
 */
export function filterAuditLogsByDays(logs = [], days = 7) {
  const daysNum = Number(days)
  if (!Number.isFinite(daysNum) || daysNum <= 0) return []

  const since = Date.now() - daysNum * 24 * 60 * 60 * 1000
  return logs.filter((log) => {
    const time = Date.parse(log?.created_at || '')
    return Number.isFinite(time) && time >= since
  })
}
