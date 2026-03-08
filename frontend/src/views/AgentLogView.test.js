// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { withUiGlobal } from '../test-utils/ui.js'

const apiMocks = vi.hoisted(() => ({
  getAuditLogs: vi.fn(),
  getAuditStats: vi.fn(),
}))

const routeState = vi.hoisted(() => ({
  query: {},
}))

vi.mock('../api', () => apiMocks)
vi.mock('../api/index.js', () => apiMocks)
vi.mock('vue-router', () => ({ useRoute: () => routeState }))

import AgentLogView from './AgentLogView.vue'

describe('AgentLogView', () => {
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
    const wrapper = mount(AgentLogView, withUiGlobal())
    await flushPromises()

    expect(apiMocks.getAuditLogs).toHaveBeenCalled()
    expect(apiMocks.getAuditStats).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Agent 智能日志')
  })

  it('handles fetch errors without crashing', async () => {
    apiMocks.getAuditLogs.mockRejectedValueOnce(new Error('logs failed'))
    apiMocks.getAuditStats.mockRejectedValueOnce(new Error('stats failed'))
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    mount(AgentLogView, withUiGlobal())
    await flushPromises()

    expect(errorSpy).toHaveBeenCalled()
    errorSpy.mockRestore()
  })
})
