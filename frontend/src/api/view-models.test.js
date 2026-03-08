import { describe, expect, it } from 'vitest'
import { buildTrendSeries, filterAuditLogsByDays, normalizeAttackChain } from './view-models.js'

describe('view-model helpers', () => {
  it('buildTrendSeries supports backend date fields', () => {
    expect(buildTrendSeries([{ date: '2026-03-07', count: 3 }, { date: '2026-03-08', count: 4 }])).toEqual({
      labels: ['2026-03-07', '2026-03-08'],
      counts: [3, 4],
    })
  })

  it('normalizeAttackChain derives decisions and alert_count from flat backend rows', () => {
    expect(normalizeAttackChain({
      id: 9,
      alert_ids: '[1,2,3]',
      risk_level: 'high',
      recommendation: 'block ip',
      action_type: 'block',
      decision_status: 'pending',
    })).toMatchObject({
      alert_count: 3,
      status: 'pending',
      decisions: [{ recommendation: 'block ip', action_type: 'block', status: 'pending' }],
      alerts: [],
    })
  })

  it('filterAuditLogsByDays keeps only recent logs', () => {
    const now = new Date()
    const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString()
    const tenDaysAgo = new Date(now.getTime() - 10 * 24 * 60 * 60 * 1000).toISOString()

    expect(filterAuditLogsByDays([
      { trace_id: 'new', created_at: oneDayAgo },
      { trace_id: 'old', created_at: tenDaysAgo },
    ], 7)).toEqual([{ trace_id: 'new', created_at: oneDayAgo }])
  })
})
