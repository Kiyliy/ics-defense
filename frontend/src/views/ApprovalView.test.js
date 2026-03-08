// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { withUiGlobal } from '../test-utils/ui.js'

const apiMocks = vi.hoisted(() => ({
  getApprovals: vi.fn(),
  respondApproval: vi.fn(),
}))

const messageMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
}))

const confirmMock = vi.hoisted(() => vi.fn())

vi.mock('../api', () => apiMocks)
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: messageMocks,
    ElMessageBox: { confirm: confirmMock },
  }
})

import ApprovalView from './ApprovalView.vue'

describe('ApprovalView', () => {


  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getApprovals.mockResolvedValue({
      approvals: [
        { id: 1, trace_id: 'trace-1', tool_name: 'block_ip', tool_args: '{"ip":"1.1.1.1"}', status: 'pending', created_at: '2026-03-08' },
      ],
    })
    apiMocks.respondApproval.mockResolvedValue({})
    confirmMock.mockResolvedValue(undefined)
  })

  it('loads pending approvals on mount', async () => {
    const wrapper = mount(ApprovalView, withUiGlobal())
    await flushPromises()

    expect(apiMocks.getApprovals).toHaveBeenCalledWith({ status: 'pending' })
    expect(wrapper.text()).toContain('审批队列')
  })

  it('switches to all tab and fetches without status filter', async () => {
    const wrapper = mount(ApprovalView, withUiGlobal())
    await flushPromises()

    wrapper.vm.activeTab = 'all'
    await wrapper.vm.fetchApprovals()

    expect(apiMocks.getApprovals).toHaveBeenLastCalledWith({})
  })

  it('approves item after confirmation and refreshes list', async () => {
    const wrapper = mount(ApprovalView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.handleApprove({ id: 7, tool_name: 'block_ip' })

    expect(confirmMock).toHaveBeenCalled()
    expect(apiMocks.respondApproval).toHaveBeenCalledWith(7, 'approved')
    expect(messageMocks.success).toHaveBeenCalledWith('已批准')
    expect(apiMocks.getApprovals).toHaveBeenCalledTimes(2)
  })

  it('ignores user-cancelled approval confirmation', async () => {
    confirmMock.mockRejectedValueOnce('cancel')
    const wrapper = mount(ApprovalView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.handleApprove({ id: 7, tool_name: 'block_ip' })

    expect(apiMocks.respondApproval).not.toHaveBeenCalled()
    expect(messageMocks.error).not.toHaveBeenCalled()
  })

  it('shows error when approval request fails', async () => {
    apiMocks.respondApproval.mockRejectedValueOnce(new Error('approve failed'))
    const wrapper = mount(ApprovalView, withUiGlobal())
    await flushPromises()

    await wrapper.vm.handleApprove({ id: 7, tool_name: 'block_ip' })

    expect(messageMocks.error).toHaveBeenCalledWith('操作失败')
  })

  it('opens reject dialog and submits rejection reason', async () => {
    const wrapper = mount(ApprovalView, withUiGlobal())
    await flushPromises()

    wrapper.vm.handleReject({ id: 8, tool_name: 'shutdown_plc' })
    expect(wrapper.vm.rejectDialogVisible).toBe(true)
    wrapper.vm.rejectReason = '风险太高'

    await wrapper.vm.confirmReject()

    expect(apiMocks.respondApproval).toHaveBeenCalledWith(8, 'rejected', '风险太高')
    expect(messageMocks.success).toHaveBeenCalledWith('已拒绝')
    expect(wrapper.vm.rejectDialogVisible).toBe(false)
  })

  it('shows error when rejection fails', async () => {
    apiMocks.respondApproval.mockRejectedValueOnce(new Error('reject failed'))
    const wrapper = mount(ApprovalView, withUiGlobal())
    await flushPromises()

    wrapper.vm.handleReject({ id: 8, tool_name: 'shutdown_plc' })
    wrapper.vm.rejectReason = '不安全'
    await wrapper.vm.confirmReject()

    expect(messageMocks.error).toHaveBeenCalledWith('操作失败')
  })
})
