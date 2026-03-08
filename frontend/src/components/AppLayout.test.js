// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { withUiGlobal } from '../test-utils/ui.js'

const apiMocks = vi.hoisted(() => ({
  getBackendHealth: vi.fn(),
  getAgentStatus: vi.fn(),
}))

vi.mock('../api/index.js', () => apiMocks)
vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/dashboard' }),
  useRouter: () => ({
    options: {
      routes: [
        {
          path: '/',
          children: [
            { path: '/dashboard', meta: { title: '指挥面板', icon: 'Monitor' } },
            { path: '/alerts', meta: { title: '告警列表', icon: 'Bell' } },
          ],
        },
      ],
    },
    push: vi.fn(),
  }),
}))

import AppLayout from './AppLayout.vue'

describe('AppLayout', () => {
  const mountLayout = () => mount(AppLayout, withUiGlobal({
    global: {
      stubs: {
        'router-view': { template: '<div><slot /></div>' },
      },
    },
  }))

  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getBackendHealth.mockResolvedValue({ status: 'ok', timestamp: '2026-03-08T15:00:00Z' })
    apiMocks.getAgentStatus.mockResolvedValue({ status: 'ok', mcp_servers: ['memory'], running_tasks: 1 })
  })

  it('shows live health statuses after refresh', async () => {
    const wrapper = mountLayout()
    await flushPromises()
    expect(apiMocks.getBackendHealth).toHaveBeenCalled()
    expect(apiMocks.getAgentStatus).toHaveBeenCalled()
    expect(wrapper.vm.systemHealth.backend).toBe('healthy')
    expect(wrapper.vm.systemHealth.agent).toBe('healthy')
  })

  it('marks degraded state when health checks fail', async () => {
    apiMocks.getBackendHealth.mockRejectedValueOnce(new Error('down'))
    apiMocks.getAgentStatus.mockRejectedValueOnce(new Error('down'))

    const wrapper = mountLayout()
    await flushPromises()

    expect(wrapper.vm.systemHealth.backend).toBe('degraded')
    expect(wrapper.vm.systemHealth.agent).toBe('degraded')
  })

  it('shows checking state before async health requests resolve', () => {
    apiMocks.getBackendHealth.mockImplementation(() => new Promise(() => {}))
    apiMocks.getAgentStatus.mockImplementation(() => new Promise(() => {}))

    const wrapper = mountLayout()

    expect(wrapper.vm.systemHealth.backend).toBe('checking')
    expect(wrapper.vm.systemHealth.agent).toBe('checking')
  })
})
