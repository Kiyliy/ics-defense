import { describe, expect, it, vi, beforeEach } from 'vitest'

const { httpClient } = vi.hoisted(() => ({
  httpClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    interceptors: {
      response: {
        use: vi.fn(),
      },
    },
  },
}))

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => httpClient),
  },
}))

import * as api from './index.js'

beforeEach(() => {
  httpClient.get.mockReset()
  httpClient.post.mockReset()
  httpClient.patch.mockReset()
  vi.unstubAllGlobals()
})

describe('frontend api client', () => {
  it('registers response interceptor that unwraps data and rethrows errors', async () => {
    expect(httpClient.interceptors.response.use).toHaveBeenCalled()

    const [onSuccess, onError] = httpClient.interceptors.response.use.mock.calls[0]
    expect(onSuccess({ data: { ok: true } })).toEqual({ ok: true })

    const error = new Error('network')
    await expect(onError(error)).rejects.toBe(error)
  })

  it('maps dashboard, alerts, analysis, approval, and audit helpers to http methods', async () => {
    httpClient.get.mockResolvedValue('get-ok')
    httpClient.post.mockResolvedValue('post-ok')
    httpClient.patch.mockResolvedValue('patch-ok')

    expect(await api.getDashboardStats()).toBe('get-ok')
    expect(httpClient.get).toHaveBeenLastCalledWith('/dashboard/stats')

    expect(await api.getBackendHealth()).toBe('get-ok')
    expect(httpClient.get).toHaveBeenLastCalledWith('/health')

    expect(await api.getAlerts({ severity: 'high' })).toBe('get-ok')
    expect(httpClient.get).toHaveBeenLastCalledWith('/alerts', { params: { severity: 'high' } })

    expect(await api.getAlertDetail(7)).toBe('get-ok')
    expect(httpClient.get).toHaveBeenLastCalledWith('/alerts/7')

    expect(await api.analyzeAlerts([1, 2])).toBe('post-ok')
    expect(httpClient.post).toHaveBeenLastCalledWith('/analysis/alerts', { alert_ids: [1, 2] })

    expect(await api.chatWithAI([{ role: 'user', content: 'hi' }])).toBe('post-ok')
    expect(httpClient.post).toHaveBeenLastCalledWith('/analysis/chat', { messages: [{ role: 'user', content: 'hi' }] })

    expect(await api.getAttackChains()).toBe('get-ok')
    expect(httpClient.get).toHaveBeenLastCalledWith('/analysis/chains')

    expect(await api.updateDecision(3, 'accepted')).toBe('patch-ok')
    expect(httpClient.patch).toHaveBeenLastCalledWith('/analysis/decisions/3', { status: 'accepted' })

    expect(await api.getApprovals({ status: 'pending' })).toBe('get-ok')
    expect(httpClient.get).toHaveBeenLastCalledWith('/approval', { params: { status: 'pending' } })

    expect(await api.respondApproval(4, 'approved', 'ok')).toBe('patch-ok')
    expect(httpClient.patch).toHaveBeenLastCalledWith('/approval/4', { status: 'approved', reason: 'ok' })

    expect(await api.getAuditLogs({ trace_id: 't-1' })).toBe('get-ok')
    expect(httpClient.get).toHaveBeenLastCalledWith('/audit', { params: { trace_id: 't-1' } })

    expect(await api.getAuditStats()).toBe('get-ok')
    expect(httpClient.get).toHaveBeenLastCalledWith('/audit/stats', { params: {} })
  })

  it('fetches agent status via fetch and rejects non-ok responses', async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ status: 'ok', running_tasks: 1 }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
      })

    await expect(api.getAgentStatus({ url: 'http://agent.local/status', fetchImpl }))
      .resolves.toEqual({ status: 'ok', running_tasks: 1 })

    expect(fetchImpl).toHaveBeenNthCalledWith(1, 'http://agent.local/status', {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    await expect(api.getAgentStatus({ url: 'http://agent.local/status', fetchImpl }))
      .rejects.toThrow('Agent status request failed with 503')
  })
})
