import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMocks = vi.hoisted(() => ({
  getAlerts: vi.fn(),
  getAlertDetail: vi.fn(),
  analyzeAlerts: vi.fn(),
}))

vi.mock('../src/api', () => apiMocks)

import { useAlertStore } from '../src/stores/alert.js'

describe('useAlertStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchAlerts maps filters to params and stores results', async () => {
    const store = useAlertStore()
    store.setFilters({ severity: 'high', source: 'waf', status: 'open', page: 2, limit: 10 })
    apiMocks.getAlerts.mockResolvedValue({
      alerts: [{ id: 1, title: 'SQL Injection' }],
      total: 9,
    })

    await store.fetchAlerts()

    expect(apiMocks.getAlerts).toHaveBeenCalledWith({
      severity: 'high',
      source: 'waf',
      status: 'open',
      limit: 10,
      offset: 10,
    })
    expect(store.alerts).toEqual([{ id: 1, title: 'SQL Injection' }])
    expect(store.total).toBe(9)
    expect(store.loading).toBe(false)
  })

  it('fetchAlerts clears state on API failure', async () => {
    const store = useAlertStore()
    apiMocks.getAlerts.mockRejectedValue(new Error('network'))

    await store.fetchAlerts()

    expect(store.alerts).toEqual([])
    expect(store.total).toBe(0)
    expect(store.loading).toBe(false)
  })

  it('fetchAlertDetail stores fetched detail and clears stale detail on failure', async () => {
    const store = useAlertStore()
    apiMocks.getAlertDetail.mockResolvedValueOnce({ id: 7, title: 'Detail' })

    await store.fetchAlertDetail(7)

    expect(apiMocks.getAlertDetail).toHaveBeenCalledWith(7)
    expect(store.currentAlert).toEqual({ id: 7, title: 'Detail' })

    apiMocks.getAlertDetail.mockRejectedValueOnce(new Error('detail failed'))
    await store.fetchAlertDetail(8)

    expect(apiMocks.getAlertDetail).toHaveBeenLastCalledWith(8)
    expect(store.currentAlert).toBeNull()
  })

  it('submitAnalysis returns null when no rows are selected and forwards selected ids otherwise', async () => {
    const store = useAlertStore()
    expect(await store.submitAnalysis()).toBeNull()

    store.toggleSelection([1, 2, 3])
    apiMocks.analyzeAlerts.mockResolvedValue({ trace_id: 'trace-1' })

    await expect(store.submitAnalysis()).resolves.toEqual({ trace_id: 'trace-1' })
    expect(apiMocks.analyzeAlerts).toHaveBeenCalledWith([1, 2, 3])
  })
})
