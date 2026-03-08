// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const apiMocks = vi.hoisted(() => ({
  getAuditLogs: vi.fn(),
  getAuditStats: vi.fn(),
}))

const routeState = vi.hoisted(() => ({
  query: {},
}))

vi.mock('../api', () => apiMocks)
vi.mock('vue-router', () => ({ useRoute: () => routeState }))

import AuditView from './AuditView.vue'

describe('AuditView', () => {
  const stubs = {
    'el-card': { template: '<div><slot /><slot name="header" /></div>' },
    'el-form': { template: '<form><slot /></form>' },
    'el-form-item': { template: '<div><slot /></div>' },
    'el-input': { template: '<input />' },
    'el-select': { template: '<select><slot /></select>' },
    'el-option': { template: '<option><slot /></option>' },
    'el-button': { template: '<button><slot /></button>' },
    'el-icon': { template: '<span><slot /></span>' },
    'el-row': { template: '<div><slot /></div>' },
    'el-col': { template: '<div><slot /></div>' },
    'el-collapse': { template: '<div><slot /></div>' },
    'el-collapse-item': { template: '<div><slot /><slot name="title" /></div>' },
    'el-table': { template: '<div><slot /></div>' },
    'el-table-column': true,
    'el-popover': { template: '<div><slot /><slot name="reference" /></div>' },
    'el-tag': { template: '<span><slot /></span>' },
    'el-empty': { template: '<div><slot /></div>' },
    Search: { template: '<i />' },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    routeState.query = {}
    apiMocks.getAuditLogs.mockResolvedValue({
      logs: [
        { trace_id: 'trace-1', event_type: 'tool_call', data: { ok: true }, token_usage: null, created_at: new Date().toISOString() },
        { trace_id: 'trace-2', event_type: 'error', data: 'boom', token_usage: '123', created_at: new Date().toISOString() },
      ],
    })
    apiMocks.getAuditStats.mockResolvedValue({
      total_analyses: 3,
      total_input_tokens: 10,
      total_output_tokens: 5,
    })
  })

  it('loads logs and stats on mount', async () => {
    const wrapper = mount(AuditView, { global: { stubs } })
    await flushPromises()

    expect(apiMocks.getAuditLogs).toHaveBeenCalledWith({})
    expect(apiMocks.getAuditStats).toHaveBeenCalledWith({ days: 7 })
    expect(wrapper.text()).toContain('审计日志')
  })

  it('initializes filters from route query', async () => {
    routeState.query = { trace_id: 'trace-route', days: '3' }
    const wrapper = mount(AuditView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.vm.filters.trace_id).toBe('trace-route')
    expect(wrapper.vm.filters.days).toBe(3)
    expect(apiMocks.getAuditLogs).toHaveBeenCalledWith({ trace_id: 'trace-route' })
    expect(apiMocks.getAuditStats).toHaveBeenCalledWith({ days: 3 })
  })

  it('fetchLogs applies current trace filter and days post-filter', async () => {
    const oldDate = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString()
    apiMocks.getAuditLogs.mockResolvedValue({
      logs: [
        { trace_id: 'trace-new', created_at: new Date().toISOString(), event_type: 'plan', data: {} },
        { trace_id: 'trace-old', created_at: oldDate, event_type: 'plan', data: {} },
      ],
    })
    const wrapper = mount(AuditView, { global: { stubs } })
    await flushPromises()

    wrapper.vm.filters.trace_id = 'trace-new'
    wrapper.vm.filters.days = 7
    await wrapper.vm.fetchLogs()

    expect(apiMocks.getAuditLogs).toHaveBeenLastCalledWith({ trace_id: 'trace-new' })
    expect(wrapper.vm.logs).toHaveLength(1)
    expect(wrapper.vm.logs[0].trace_id).toBe('trace-new')
  })

  it('handleReset restores defaults and refetches data', async () => {
    const wrapper = mount(AuditView, { global: { stubs } })
    await flushPromises()

    wrapper.vm.filters = { trace_id: 'abc', days: 30 }
    wrapper.vm.handleReset()
    await flushPromises()

    expect(wrapper.vm.filters).toEqual({ trace_id: '', days: 7 })
    expect(apiMocks.getAuditStats).toHaveBeenLastCalledWith({ days: 7 })
  })

  it('handles fetch errors without crashing', async () => {
    apiMocks.getAuditLogs.mockRejectedValueOnce(new Error('logs failed'))
    apiMocks.getAuditStats.mockRejectedValueOnce(new Error('stats failed'))
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    mount(AuditView, { global: { stubs } })
    await flushPromises()

    expect(errorSpy).toHaveBeenCalled()
    errorSpy.mockRestore()
  })

  it('formats and truncates data safely', async () => {
    const wrapper = mount(AuditView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.vm.eventTypeColor('error')).toBe('danger')
    expect(wrapper.vm.truncateData('x'.repeat(100))).toContain('...')
    expect(wrapper.vm.formatData('{"a":1}')).toContain('"a": 1')
    expect(wrapper.vm.formatData('plain')).toBe('plain')
  })
})
