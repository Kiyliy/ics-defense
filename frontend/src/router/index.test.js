import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerMocks = vi.hoisted(() => ({
  createRouterMock: vi.fn((options) => ({
    options,
    beforeEach: vi.fn((handler) => {
      routerMocks.createRouterMock.guard = handler
    }),
  })),
  createWebHistoryMock: vi.fn(() => ({ mode: 'history' })),
}))

vi.mock('vue-router', () => ({
  createRouter: routerMocks.createRouterMock,
  createWebHistory: routerMocks.createWebHistoryMock,
}))
vi.mock('../components/AppLayout.vue', () => ({ default: { name: 'AppLayout' } }))
vi.mock('../views/DashboardView.vue', () => ({ default: { name: 'DashboardView' } }))
vi.mock('../views/AlertListView.vue', () => ({ default: { name: 'AlertListView' } }))
vi.mock('../views/AttackChainView.vue', () => ({ default: { name: 'AttackChainView' } }))
vi.mock('../views/ChatView.vue', () => ({ default: { name: 'ChatView' } }))
vi.mock('../views/ApprovalView.vue', () => ({ default: { name: 'ApprovalView' } }))
vi.mock('../views/AuditView.vue', () => ({ default: { name: 'AuditView' } }))

import router from './index.js'

describe('router/index', () => {
  beforeEach(() => {
    delete global.document
  })

  it('creates history router with expected top-level routes', () => {
    expect(routerMocks.createWebHistoryMock).toHaveBeenCalled()
    expect(routerMocks.createRouterMock).toHaveBeenCalled()
    expect(router.options.routes).toHaveLength(1)
    expect(router.options.routes[0].redirect).toBe('/dashboard')
    expect(router.options.routes[0].children.map((route) => route.name)).toEqual([
      'Dashboard', 'Alerts', 'AttackChains', 'Chat', 'Approval', 'Audit',
    ])
  })

  it('sets document title in beforeEach guard', () => {
    global.document = { title: '' }

    routerMocks.createRouterMock.guard({ meta: { title: '审计日志' } })
    expect(global.document.title).toBe('审计日志 - ICS Security')

    routerMocks.createRouterMock.guard({ meta: {} })
    expect(global.document.title).toBe('ICS Security')
  })
})
