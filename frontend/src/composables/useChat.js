import { ref, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { chatWithAI } from '../api'
import { renderMarkdownSafe } from '../api/markdown.js'

export function useChat() {
  const conversations = ref([{ title: '新对话', messages: [] }])
  const currentConvIndex = ref(0)
  const inputText = ref('')
  const sending = ref(false)
  const messageArea = ref(null)
  const maxChars = 2000

  const currentMessages = computed(() => {
    return (conversations.value[currentConvIndex.value]?.messages || []).map((msg) => {
      if (msg.role === 'assistant' && msg._parsed === undefined) {
        msg._parsed = parseAIResponse(msg.content)
      }
      return msg
    })
  })

  function parseAIResponse(content) {
    if (!content || typeof content !== 'string') return null
    try {
      const parsed = JSON.parse(content)
      if (parsed && typeof parsed === 'object' && (parsed.analysis || parsed.recommendation || parsed.risk_level)) {
        return parsed
      }
      return null
    } catch {
      return null
    }
  }

  function renderMarkdown(text) {
    return renderMarkdownSafe(text)
  }

  function shouldShowTimestamp(idx) {
    return idx % 5 === 0
  }

  function getMessageTime(msg) {
    if (msg.timestamp) return msg.timestamp
    return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }

  function newConversation() {
    conversations.value.push({ title: '新对话', messages: [] })
    currentConvIndex.value = conversations.value.length - 1
  }

  function switchConversation(idx) {
    currentConvIndex.value = idx
  }

  async function scrollToBottom() {
    await nextTick()
    if (messageArea.value) {
      messageArea.value.scrollTop = messageArea.value.scrollHeight
    }
  }

  async function handleSend() {
    const text = inputText.value.trim()
    if (!text || sending.value) return

    const conv = conversations.value[currentConvIndex.value]
    conv.messages.push({ role: 'user', content: text })

    if (conv.messages.length === 1) {
      conv.title = text.slice(0, 20) + (text.length > 20 ? '...' : '')
    }

    inputText.value = ''
    sending.value = true
    await scrollToBottom()

    try {
      const apiMessages = conv.messages.map((m) => ({
        role: m.role,
        content: m.content,
      }))
      const res = await chatWithAI(apiMessages)
      conv.messages.push({ role: 'assistant', content: res.reply || '无响应内容' })
    } catch (err) {
      ElMessage.error('发送失败，请重试')
      conv.messages.push({
        role: 'assistant',
        content: '抱歉，请求失败，请检查网络或稍后重试。',
      })
    } finally {
      sending.value = false
      await scrollToBottom()
    }
  }

  return {
    conversations,
    currentConvIndex,
    inputText,
    sending,
    messageArea,
    maxChars,
    currentMessages,
    renderMarkdown,
    shouldShowTimestamp,
    getMessageTime,
    newConversation,
    switchConversation,
    handleSend,
  }
}
