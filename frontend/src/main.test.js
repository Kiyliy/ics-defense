import { beforeEach, describe, expect, it, vi } from 'vitest'

const appMocks = vi.hoisted(() => {
  const app = {
    component: vi.fn(),
    use: vi.fn(),
    mount: vi.fn(),
  }
  return {
    app,
    createApp: vi.fn(() => app),
    createPinia: vi.fn(() => ({ pinia: true })),
  }
})

vi.mock('vue', () => ({ createApp: appMocks.createApp }))
vi.mock('pinia', () => ({ createPinia: appMocks.createPinia }))
vi.mock('./App.vue', () => ({ default: { name: 'App' } }))
vi.mock('./router', () => ({ default: { name: 'router' } }))
vi.mock('./styles/global.css', () => ({}))
vi.mock('@element-plus/icons-vue', () => ({
  Bell: { name: 'Bell' },
  ChatDotRound: { name: 'ChatDotRound' },
  Checked: { name: 'Checked' },
  Connection: { name: 'Connection' },
  DataAnalysis: { name: 'DataAnalysis' },
  Document: { name: 'Document' },
  Expand: { name: 'Expand' },
  Fold: { name: 'Fold' },
  Loading: { name: 'Loading' },
  Lock: { name: 'Lock' },
  MagicStick: { name: 'MagicStick' },
  Monitor: { name: 'Monitor' },
  Notification: { name: 'Notification' },
  Plus: { name: 'Plus' },
  Promotion: { name: 'Promotion' },
  Search: { name: 'Search' },
  Setting: { name: 'Setting' },
  Warning: { name: 'Warning' },
}))

describe('main.js', () => {
  beforeEach(() => {
    vi.resetModules()
    appMocks.createApp.mockClear()
    appMocks.createPinia.mockClear()
    appMocks.app.component.mockClear()
    appMocks.app.use.mockClear()
    appMocks.app.mount.mockClear()
  })

  it('creates app, registers icons, installs pinia and router, then mounts', async () => {
    await import('./main.js')

    expect(appMocks.createApp).toHaveBeenCalled()
    expect(appMocks.createPinia).toHaveBeenCalled()
    expect(appMocks.app.component).toHaveBeenCalledTimes(18)
    expect(appMocks.app.component).toHaveBeenCalledWith('Bell', expect.any(Object))
    expect(appMocks.app.component).toHaveBeenCalledWith('Warning', expect.any(Object))
    expect(appMocks.app.use).toHaveBeenCalledTimes(2)
    expect(appMocks.app.mount).toHaveBeenCalledWith('#app')
  })
})
