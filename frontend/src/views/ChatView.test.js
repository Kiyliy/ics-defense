// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { withUiGlobal } from '../test-utils/ui.js'

const apiMocks = vi.hoisted(() => ({
  chatWithAI: vi.fn(),
}))

const markdownMocks = vi.hoisted(() => ({
  renderMarkdownSafe: vi.fn((text) => `<p>${text}</p>`),
}))

const messageMocks = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }))

vi.mock('../api', () => apiMocks)
vi.mock('../api/markdown.js', () => markdownMocks)
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return { ...actual, ElMessage: messageMocks }
})

import ChatView from './ChatView.vue'

describe('ChatView', () => {
  const stubs = undefined

  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.chatWithAI.mockResolvedValue({ reply: 'plain reply' })
  })

  it('starts with empty conversation state and can create a new conversation', async () => {
    const wrapper = mount(ChatView, withUiGlobal())

    expect(wrapper.text()).toContain('开始与 AI 安全助手对话')
    expect(wrapper.vm.conversations).toHaveLength(1)

    wrapper.vm.newConversation()
    await flushPromises()

    expect(wrapper.vm.conversations).toHaveLength(2)
    expect(wrapper.vm.currentConvIndex).toBe(1)
  })

  it('sends user message, renames first conversation and appends assistant reply', async () => {
    const wrapper = mount(ChatView, withUiGlobal())
    wrapper.vm.inputText = '请分析当前风险态势'

    await wrapper.vm.handleSend()
    await flushPromises()

    expect(apiMocks.chatWithAI).toHaveBeenCalledWith([
      { role: 'user', content: '请分析当前风险态势' },
    ])
    expect(wrapper.vm.conversations[0].title).toContain('请分析当前风险态势')
    expect(wrapper.vm.currentMessages).toHaveLength(2)
    expect(wrapper.vm.currentMessages[1].content).toBe('plain reply')
  })

  it('parses structured assistant JSON and maps risk tag types', () => {
    const wrapper = mount(ChatView, withUiGlobal())
    const parsed = wrapper.vm.parseAIResponse(JSON.stringify({
      analysis: '发现异常',
      recommendation: '隔离主机',
      risk_level: 'high',
      confidence: 0.8,
    }))

    expect(parsed.recommendation).toBe('隔离主机')
    expect(wrapper.vm.parseAIResponse('not json')).toBeNull()
    expect(wrapper.vm.riskTagType('high')).toBe('danger')
    expect(wrapper.vm.riskTagType('中')).toBe('warning')
    expect(wrapper.vm.riskTagType('low')).toBe('success')
    expect(wrapper.vm.riskTagType('unknown')).toBe('info')
  })

  it('uses safe markdown renderer and falls back with error message on request failure', async () => {
    apiMocks.chatWithAI.mockRejectedValueOnce(new Error('network'))
    const wrapper = mount(ChatView, withUiGlobal())

    expect(wrapper.vm.renderMarkdown('hello')).toBe('<p>hello</p>')
    expect(markdownMocks.renderMarkdownSafe).toHaveBeenCalledWith('hello')

    wrapper.vm.inputText = '第二条消息'
    await wrapper.vm.handleSend()
    await flushPromises()

    expect(messageMocks.error).toHaveBeenCalledWith('发送失败，请重试')
    expect(wrapper.vm.currentMessages.at(-1).content).toContain('抱歉，请求失败')
    expect(wrapper.vm.sending).toBe(false)
  })

  it('switches active conversation', async () => {
    const wrapper = mount(ChatView, withUiGlobal())
    wrapper.vm.newConversation()
    await flushPromises()

    wrapper.vm.switchConversation(0)
    expect(wrapper.vm.currentConvIndex).toBe(0)
  })
})
