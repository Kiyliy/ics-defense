import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerState = vi.hoisted(() => ({
  guard: null,
  routerInstance: null,
}))

const routerMocks = vi.hoisted(() => {
  const createRouterMock = vi.fn((options) => {
    const instance = {
      options,
      beforeEach: vi.fn((handler) => {
        routerState.guard = handler
      }),
    }
    routerState.routerInstance = instance
    return instance
  })

  return {
    createRouterMock,
    createWebHistoryMock: vi.fn(() => ({ mode: 'history' })),
  }
})

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
vi.mock('../views/AgentLogView.vue', () => ({ default: { name: 'AgentLogView' } }))
vi.mock('../views/NotificationView.vue', () => ({ default: { name: 'NotificationView' } }))
vi.mock('../views/SettingsView.vue', () => ({ default: { name: 'SettingsView' } }))

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
      'Dashboard', 'Chat', 'Alerts', 'AttackChains', 'Approval', 'AgentLogs', 'Notifications', 'Settings',
    ])
  })

  it('sets document title in beforeEach guard', () => {
    global.document = { title: '' }

    routerState.guard({ meta: { title: '审计日志' } })
    expect(global.document.title).toBe('审计日志 - ICS Security')

    routerState.guard({ meta: {} })
    expect(global.document.title).toBe('ICS Security')
  })
})
