// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { withUiGlobal } from '../test-utils/ui.js'

const routerPush = vi.fn()
const messageMocks = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }))
const store = {
  alerts: ref([]),
  total: ref(0),
  loading: ref(false),
  currentAlert: ref(null),
  selectedIds: ref([]),
  filters: ref({ severity: '', source: '', status: '', page: 1, limit: 20 }),
  fetchAlerts: vi.fn(),
  fetchAlertDetail: vi.fn(),
  submitAnalysis: vi.fn(),
  pollAnalysisResult: vi.fn(),
  setFilters: vi.fn(),
  toggleSelection: vi.fn(),
}

vi.mock('../stores/alert', () => ({ useAlertStore: () => store }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return { ...actual, ElMessage: messageMocks }
})

import AlertListView from './AlertListView.vue'

describe('AlertListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.fetchAlerts.mockResolvedValue()
    store.fetchAlertDetail.mockResolvedValue({ id: 1, title: 'detail' })
    store.pollAnalysisResult.mockResolvedValue(null)
  })

  it('loads alerts on mount and resets filters', async () => {
const wrapper = mount(AlertListView, withUiGlobal())
    await flushPromises()
    expect(store.fetchAlerts).toHaveBeenCalled()
    wrapper.vm.handleReset()
    expect(store.setFilters).toHaveBeenCalledWith({ severity: '', source: '', status: '', page: 1 })
  })

  it('submits analysis, refreshes list, starts polling and routes to chains when trace_id exists', async () => {
    store.submitAnalysis.mockResolvedValueOnce({ trace_id: 'trace-1' })
const wrapper = mount(AlertListView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.handleAnalyze()

    expect(store.toggleSelection).toHaveBeenCalledWith([])
    expect(store.fetchAlerts).toHaveBeenCalledTimes(2)
    expect(store.pollAnalysisResult).toHaveBeenCalledWith('trace-1')
    expect(routerPush).toHaveBeenCalledWith({ path: '/chains' })
  })

  it('routes to chains when direct analysis result returns attack_chain_id', async () => {
    store.submitAnalysis.mockResolvedValueOnce({ attack_chain_id: 88 })

const wrapper = mount(AlertListView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.handleAnalyze()

    expect(routerPush).toHaveBeenCalledWith('/chains')
  })

  it('shows error message when analysis submission fails', async () => {
    store.submitAnalysis.mockResolvedValueOnce(null)

const wrapper = mount(AlertListView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.handleAnalyze()

    expect(messageMocks.error).toHaveBeenCalled()
  })

  it('shows warning when detail fetch fails', async () => {
    store.fetchAlertDetail.mockResolvedValueOnce(null)
const wrapper = mount(AlertListView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.showDetail({ id: 3, title: 'summary' })

    expect(messageMocks.warning).toHaveBeenCalled()
  })
})
