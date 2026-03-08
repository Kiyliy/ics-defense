// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { withUiGlobal } from '../test-utils/ui.js'

const apiMocks = vi.hoisted(() => ({
  getDashboardStats: vi.fn(),
  getDashboardTrend: vi.fn(),
  getAlerts: vi.fn(),
}))

const chartMocks = vi.hoisted(() => ({
  init: vi.fn(() => ({ setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn() })),
  use: vi.fn(),
  graphic: { LinearGradient: vi.fn(() => ({ kind: 'gradient' })) },
}))

vi.mock('../api', () => apiMocks)
vi.mock('echarts/core', () => chartMocks)
vi.mock('echarts/charts', () => ({ LineChart: {} }))
vi.mock('echarts/components', () => ({ GridComponent: {}, TooltipComponent: {} }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

import DashboardView from './DashboardView.vue'

describe('DashboardView', () => {


  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getDashboardStats.mockResolvedValue({
      summary: { totalAlerts: 12, totalChains: 3, pendingDecisions: 2 },
      alertsBySeverity: [{ severity: 'high', count: 2 }, { severity: 'critical', count: 1 }],
    })
    apiMocks.getDashboardTrend.mockResolvedValue({ trend: [{ date: '2026-03-07', count: 4 }] })
    apiMocks.getAlerts.mockResolvedValue({ alerts: [{ id: 1, title: 'A1', severity: 'high', status: 'open' }] })
  })

  it('loads stats, trend, and recent alerts then renders chart', async () => {
    const wrapper = mount(DashboardView, withUiGlobal({
      global: {
        stubs: { StatCard: { template: '<div><slot /></div>' } },
        mocks: { $router: { push: vi.fn() } },
      },
    }))

    await flushPromises()

    expect(apiMocks.getDashboardStats).toHaveBeenCalled()
    expect(apiMocks.getDashboardTrend).toHaveBeenCalled()
    expect(apiMocks.getAlerts).toHaveBeenCalledWith({ page: 1, limit: 10 })
    expect(wrapper.find('.page-title').text()).toBe('仪表盘')
  })

  it('handles dashboard loading errors without crashing', async () => {
    apiMocks.getDashboardStats.mockRejectedValueOnce(new Error('dashboard failed'))
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    mount(DashboardView, withUiGlobal({
      global: { stubs: { StatCard: { template: '<div><slot /></div>' } } },
    }))
    await flushPromises()

    expect(errorSpy).toHaveBeenCalled()
    errorSpy.mockRestore()
  })

  it('maps mixed severity buckets into high alert count', async () => {
    apiMocks.getDashboardStats.mockResolvedValueOnce({
      summary: { totalAlerts: 8, totalChains: 1, pendingDecisions: 0 },
      alertsBySeverity: [
        { severity: 'low', count: 3 },
        { severity: 'high', count: 2 },
        { severity: 'critical', count: 4 },
      ],
    })

    mount(DashboardView, withUiGlobal({
      global: { stubs: { StatCard: { template: '<div><slot /></div>' } } },
    }))
    await flushPromises()

    expect(apiMocks.getDashboardStats).toHaveBeenCalledTimes(1)
    expect(apiMocks.getDashboardTrend).toHaveBeenCalledTimes(1)
  })
})
