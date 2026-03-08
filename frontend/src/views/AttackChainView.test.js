// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { withUiGlobal } from '../test-utils/ui.js'

const apiMocks = vi.hoisted(() => ({
  getAttackChains: vi.fn(),
  updateDecision: vi.fn(),
}))

const messageMocks = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock('../api', () => apiMocks)
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return { ...actual, ElMessage: messageMocks }
})

import AttackChainView from './AttackChainView.vue'

describe('AttackChainView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getAttackChains.mockResolvedValue({
      chains: [{ id: 1, name: 'Chain', risk_level: 'high', alert_count: 2, status: 'pending', decisions: [{ id: 9, status: 'pending', recommendation: 'block ip' }], alerts: [] }],
    })
    apiMocks.updateDecision.mockResolvedValue({ updated: true })
  })

  it('loads chain data on mount', async () => {
    const wrapper = mount(AttackChainView, withUiGlobal())
    await flushPromises()
    expect(apiMocks.getAttackChains).toHaveBeenCalled()
    expect(wrapper.text()).toContain('攻击链分析')
  })

  it('updates decision and refreshes list', async () => {
    const wrapper = mount(AttackChainView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.handleDecision(9, 'accepted')

    expect(apiMocks.updateDecision).toHaveBeenCalledWith(9, 'accepted')
    expect(messageMocks.success).toHaveBeenCalled()
    expect(apiMocks.getAttackChains).toHaveBeenCalledTimes(2)
  })

  it('shows error message when decision update fails', async () => {
    apiMocks.updateDecision.mockRejectedValueOnce(new Error('update failed'))

    const wrapper = mount(AttackChainView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.handleDecision(9, 'accepted')

    expect(messageMocks.error).toHaveBeenCalled()
  })
})
