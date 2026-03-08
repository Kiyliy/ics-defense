import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMocks = vi.hoisted(() => ({
  getAlerts: vi.fn(),
  getAlertDetail: vi.fn(),
  analyzeAlerts: vi.fn(),
}))

vi.mock('../api', () => apiMocks)

import { useAlertStore } from './alert.js'

describe('alert store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiMocks.getAlerts.mockReset()
    apiMocks.getAlertDetail.mockReset()
    apiMocks.analyzeAlerts.mockReset()
  })

  it('fetchAlerts builds params from filters and updates state', async () => {
    const store = useAlertStore()
    store.setFilters({ severity: 'high', source: 'waf', status: 'open', page: 2, limit: 10 })
    apiMocks.getAlerts.mockResolvedValue({ alerts: [{ id: 1 }], total: 11 })

    await store.fetchAlerts()

    expect(apiMocks.getAlerts).toHaveBeenCalledWith({
      severity: 'high',
      source: 'waf',
      status: 'open',
      limit: 10,
      offset: 10,
    })
    expect(store.alerts).toEqual([{ id: 1 }])
    expect(store.total).toBe(11)
    expect(store.loading).toBe(false)
  })

  it('fetchAlerts resets list on api failure', async () => {
    const store = useAlertStore()
    store.alerts = [{ id: 9 }]
    store.total = 5
    apiMocks.getAlerts.mockRejectedValue(new Error('boom'))

    await store.fetchAlerts()

    expect(store.alerts).toEqual([])
    expect(store.total).toBe(0)
    expect(store.loading).toBe(false)
  })

  it('fetchAlertDetail stores current alert when request succeeds', async () => {
    const store = useAlertStore()
    apiMocks.getAlertDetail.mockResolvedValue({ id: 8, title: 'alert' })

    await store.fetchAlertDetail(8)

    expect(apiMocks.getAlertDetail).toHaveBeenCalledWith(8)
    expect(store.currentAlert).toEqual({ id: 8, title: 'alert' })
  })

  it('submitAnalysis short-circuits empty selection and handles success/failure', async () => {
    const store = useAlertStore()
    expect(await store.submitAnalysis()).toBeNull()

    store.toggleSelection([1, 2])
    apiMocks.analyzeAlerts.mockResolvedValue({ attack_chain_id: 3 })
    expect(await store.submitAnalysis()).toEqual({ attack_chain_id: 3 })
    expect(apiMocks.analyzeAlerts).toHaveBeenCalledWith([1, 2])

    apiMocks.analyzeAlerts.mockRejectedValue(new Error('bad'))
    expect(await store.submitAnalysis()).toBeNull()
  })

  it('setFilters merges partial values and toggleSelection replaces ids', () => {
    const store = useAlertStore()
    store.setFilters({ severity: 'critical', page: 3 })
    store.toggleSelection([7, 8])

    expect(store.filters.severity).toBe('critical')
    expect(store.filters.page).toBe(3)
    expect(store.filters.limit).toBe(20)
    expect(store.selectedIds).toEqual([7, 8])
  })
})
