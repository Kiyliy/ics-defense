import { beforeEach, describe, expect, it, vi } from 'vitest'

const createRouterMock = vi.fn((options) => ({
  options,
  beforeEach: vi.fn((handler) => {
    createRouterMock.guard = handler
  }),
}))
const createWebHistoryMock = vi.fn(() => ({ mode: 'history' }))

vi.mock('vue-router', () => ({
  createRouter: createRouterMock,
  createWebHistory: createWebHistoryMock,
}))
vi.mock('../components/AppLayout.vue', () => ({ default: { name: 'AppLayout' } }))
vi.mock('../views/DashboardView.vue', () => ({ default: { name: 'DashboardView' } }))
vi.mock('../views/AlertListView.vue', () => ({ default: { name: 'AlertListView' } }))
vi.mock('../views/AttackChainView.vue', () => ({ default: { name: 'AttackChainView' } }))
vi.mock('../views/ChatView.vue', () => ({ default: { name: 'ChatView' } }))
vi.mock('../views/ApprovalView.vue', () => ({ default: { name: 'ApprovalView' } }))
vi.mock('../views/AuditView.vue', () => ({ default: { name: 'AuditView' } }))

describe('router/index', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    delete global.document
  })

  it('creates history router with expected top-level routes', async () => {
    const { default: router } = await import('./index.js')

    expect(createWebHistoryMock).toHaveBeenCalled()
    expect(createRouterMock).toHaveBeenCalled()
    expect(router.options.routes).toHaveLength(1)
    expect(router.options.routes[0].redirect).toBe('/dashboard')
    expect(router.options.routes[0].children.map((route) => route.name)).toEqual([
      'Dashboard', 'Alerts', 'AttackChains', 'Chat', 'Approval', 'Audit',
    ])
  })

  it('sets document title in beforeEach guard', async () => {
    global.document = { title: '' }
    await import('./index.js')

    createRouterMock.guard({ meta: { title: '审计日志' } })
    expect(global.document.title).toBe('审计日志 - ICS Security')

    createRouterMock.guard({ meta: {} })
    expect(global.document.title).toBe('ICS Security')
  })
})
