<template>
  <div>
    <div class="page-header">
      <div class="page-header-copy">
        <h2>AI 对话</h2>
        <p class="page-subtitle">
          通过结构化安全问答、MITRE 映射与行动建议，辅助分析师快速完成解释、推演和响应协同。
        </p>
      </div>
      <div class="page-header-meta">
        <span>AI Copilot</span>
        <span>{{ conversations.length }} Conversations</span>
      </div>
    </div>

    <div class="chat-layout">
      <!-- ===== Sidebar ===== -->
      <aside class="chat-sidebar">
        <button class="new-chat-btn" @click="newConversation">
          <svg viewBox="0 0 16 16" width="16" height="16"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>
          新建对话
        </button>

        <div class="conv-list">
          <div
            v-for="(conv, idx) in conversations"
            :key="idx"
            :class="['conv-item', { 'conv-item--active': currentConvIndex === idx }]"
            @click="switchConversation(idx)"
          >
            <div class="conv-item__icon">
              <svg viewBox="0 0 16 16" width="16" height="16"><path d="M2 3a2 2 0 012-2h8a2 2 0 012 2v6a2 2 0 01-2 2H6l-3 3V11a2 2 0 01-1-2V3z" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
            </div>
            <div class="conv-item__body">
              <span class="conv-item__title">{{ conv.title || `对话 ${idx + 1}` }}</span>
              <span class="conv-item__time" v-if="conv.messages && conv.messages.length">
                {{ conv.messages.length }} 条消息
              </span>
            </div>
          </div>
          <div v-if="conversations.length === 0" class="conv-empty">
            <svg viewBox="0 0 16 16" width="32" height="32" class="conv-empty__icon"><path d="M2 3a2 2 0 012-2h8a2 2 0 012 2v6a2 2 0 01-2 2H6l-3 3V11a2 2 0 01-1-2V3z" stroke="#94a3b8" stroke-width="1.5" fill="none"/></svg>
            <span>暂无对话</span>
          </div>
        </div>
      </aside>

      <!-- ===== Main chat area ===== -->
      <div class="chat-main">
        <!-- Header bar -->
        <div class="chat-main__header">
          <div class="chat-main__header-left">
            <svg viewBox="0 0 20 20" width="20" height="20"><circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M10 6v4l2.5 1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
            <div>
              <span class="chat-main__title">AI 安全分析助手</span>
              <span class="chat-main__subtitle">Structured Security Reasoning</span>
            </div>
          </div>
          <div class="online-dot"></div>
        </div>

        <!-- Messages area -->
        <div ref="messageArea" class="message-area">
          <!-- Empty state -->
          <div v-if="currentMessages.length === 0" class="empty-chat">
            <div class="empty-chat__icon-ring">
              <svg viewBox="0 0 48 48" width="48" height="48"><circle cx="24" cy="24" r="20" stroke="#94a3b8" stroke-width="1.5" fill="none" stroke-dasharray="4 3"/><path d="M16 20a8 8 0 0116 0v2a8 8 0 01-16 0v-2z" stroke="#94a3b8" stroke-width="1.5" fill="none"/><path d="M20 30l-2 6M28 30l2 6" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
            </div>
            <p class="empty-chat__title">开始与 AI 安全助手对话</p>
            <p class="empty-chat__hint">输入安全分析问题，获取结构化分析、MITRE 映射与行动建议</p>
          </div>

          <!-- Messages -->
          <template v-for="(msg, idx) in currentMessages" :key="idx">
            <!-- Timestamp separator -->
            <div v-if="idx === 0 || shouldShowTimestamp(idx)" class="timestamp-separator">
              <span>{{ getMessageTime(msg) }}</span>
            </div>

            <div :class="['message-row', msg.role]">
              <!-- Avatar -->
              <div :class="['msg-avatar', msg.role]">
                <svg v-if="msg.role === 'user'" viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="6" r="3" fill="currentColor"/><path d="M2 14a6 6 0 0112 0" fill="currentColor"/></svg>
                <svg v-else viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M5 8h6M8 5v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
              </div>

              <div :class="['chat-bubble', msg.role]">
                <template v-if="msg.role === 'assistant'">
                  <template v-if="msg._parsed">
                    <div class="ai-structured">
                      <!-- Analysis -->
                      <div class="ai-analysis" v-html="renderMarkdown(msg._parsed.analysis || '')"></div>

                      <!-- Risk & confidence tags -->
                      <div class="ai-tags" v-if="msg._parsed.risk_level || msg._parsed.confidence || msg._parsed.action_type">
                        <span v-if="msg._parsed.risk_level" :class="['ai-tag', `ai-tag--${(msg._parsed.risk_level || '').toLowerCase()}`]">
                          <svg viewBox="0 0 12 12" width="12" height="12"><path d="M6 1L1 11h10L6 1z" stroke="currentColor" stroke-width="1.2" fill="none"/></svg>
                          风险: {{ msg._parsed.risk_level }}
                        </span>
                        <span v-if="msg._parsed.confidence" class="ai-tag ai-tag--info">
                          <svg viewBox="0 0 12 12" width="12" height="12"><circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.2" fill="none"/><path d="M6 4v3M6 8.5v.01" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                          置信度: {{ msg._parsed.confidence }}
                        </span>
                        <span v-if="msg._parsed.action_type" class="ai-tag ai-tag--warning">
                          <svg viewBox="0 0 12 12" width="12" height="12"><path d="M1 6l4 4L11 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                          动作: {{ msg._parsed.action_type }}
                        </span>
                      </div>

                      <!-- MITRE fields card -->
                      <div class="mitre-card" v-if="msg._parsed.mitre_tactic || msg._parsed.mitre_technique">
                        <div class="mitre-card__header">
                          <svg viewBox="0 0 16 16" width="14" height="14"><rect x="1" y="1" width="6" height="6" rx="1" fill="currentColor"/><rect x="9" y="1" width="6" height="6" rx="1" fill="currentColor"/><rect x="1" y="9" width="6" height="6" rx="1" fill="currentColor"/><rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor"/></svg>
                          MITRE ATT&CK
                        </div>
                        <div v-if="msg._parsed.mitre_tactic" class="mitre-card__field">
                          <span class="mitre-card__label">战术 Tactic</span>
                          <span class="mitre-card__value">{{ msg._parsed.mitre_tactic }}</span>
                        </div>
                        <div v-if="msg._parsed.mitre_technique" class="mitre-card__field">
                          <span class="mitre-card__label">技术 Technique</span>
                          <span class="mitre-card__value">{{ msg._parsed.mitre_technique }}</span>
                        </div>
                      </div>

                      <!-- Rationale -->
                      <div v-if="msg._parsed.rationale" class="rationale-block">
                        <span class="rationale-block__label">
                          <svg viewBox="0 0 12 12" width="12" height="12"><path d="M6 1a5 5 0 110 10A5 5 0 016 1z" stroke="currentColor" stroke-width="1.2" fill="none"/><path d="M6 4v3M6 8.5v.01" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                          依据
                        </span>
                        <p>{{ msg._parsed.rationale }}</p>
                      </div>

                      <!-- Recommendation card -->
                      <div v-if="msg._parsed.recommendation" class="recommendation-card">
                        <div class="recommendation-card__icon">
                          <svg viewBox="0 0 16 16" width="18" height="18"><path d="M8 1l2 5h5l-4 3 1.5 5L8 11l-4.5 3L5 9 1 6h5l2-5z" stroke="#16a34a" stroke-width="1.3" fill="rgba(34,197,94,0.15)"/></svg>
                        </div>
                        <div class="recommendation-card__body">
                          <span class="recommendation-card__title">建议 Recommendation</span>
                          <p>{{ msg._parsed.recommendation }}</p>
                        </div>
                      </div>
                    </div>
                  </template>
                  <div v-else v-html="renderMarkdown(msg.content)"></div>
                </template>
                <span v-else>{{ msg.content }}</span>
              </div>
            </div>
          </template>

          <!-- Typing indicator -->
          <div v-if="sending" class="message-row assistant">
            <div class="msg-avatar assistant">
              <svg viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M5 8h6M8 5v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
            </div>
            <div class="chat-bubble assistant">
              <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </div>
            </div>
          </div>
        </div>

        <!-- ===== Input area ===== -->
        <div class="input-surface">
          <div class="input-wrapper" :class="{ 'input-wrapper--focused': inputFocused }">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="3"
              placeholder="输入安全分析问题..."
              resize="none"
              @keydown.enter.ctrl="handleSend"
              @keydown.enter.meta="handleSend"
              @focus="inputFocused = true"
              @blur="inputFocused = false"
            />
            <!-- Character progress bar -->
            <div class="char-progress">
              <div
                class="char-progress__bar"
                :style="{ width: Math.min(100, (inputText.length / maxChars) * 100) + '%' }"
                :class="{ 'char-progress__bar--warn': inputText.length > maxChars * 0.9 }"
              ></div>
            </div>
          </div>
          <div class="input-footer">
            <span class="input-hint">
              <kbd>Ctrl</kbd> + <kbd>Enter</kbd> 发送
            </span>
            <button
              class="send-button"
              :disabled="!inputText.trim() || sending"
              @click="handleSend"
            >
              <svg viewBox="0 0 16 16" width="16" height="16"><path d="M1 8l6-6v4h6a2 2 0 012 2v0a2 2 0 01-2 2H7v4L1 8z" fill="currentColor"/></svg>
              <span>发送</span>
              <span v-if="sending" class="send-button__loading"></span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { chatWithAI } from '../api'
import { renderMarkdownSafe } from '../api/markdown.js'
import { getRiskTagType } from '../utils/ui.js'

const conversations = ref([{ title: '新对话', messages: [] }])
const currentConvIndex = ref(0)
const inputText = ref('')
const sending = ref(false)
const messageArea = ref(null)
const inputFocused = ref(false)
const maxChars = 2000

const currentMessages = computed(() => {
  return (conversations.value[currentConvIndex.value]?.messages || []).map((msg) => {
    if (msg.role === 'assistant' && msg._parsed === undefined) {
      msg._parsed = parseAIResponse(msg.content)
    }
    return msg
  })
})

function renderMarkdown(text) {
  return renderMarkdownSafe(text)
}

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

function shouldShowTimestamp(idx) {
  // Show timestamp every 5 messages
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
</script>

<style scoped>
/* ===== Layout ===== */
.chat-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 20px;
  min-height: calc(100vh - 250px);
}

@media (max-width: 1024px) {
  .chat-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .chat-sidebar {
    max-height: 200px;
  }
}

/* ===== Sidebar ===== */
.chat-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--app-radius-lg, 24px);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--app-shadow-soft, 0 10px 30px rgba(15,23,42,0.1));
  backdrop-filter: blur(16px);
  overflow: hidden;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px 16px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--app-primary, #4f8cff), var(--app-primary-strong, #2563eb));
  color: #fff;
  font-size: 0.88rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.24);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.new-chat-btn:hover {
  box-shadow: 0 12px 32px rgba(37, 99, 235, 0.32);
  transform: translateY(-1px);
}

.new-chat-btn:active {
  transform: translateY(0);
}

.conv-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  flex: 1;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border-left: 3px solid transparent;
  color: #475569;
}

.conv-item:hover {
  background: rgba(79, 140, 255, 0.06);
}

.conv-item--active {
  background: linear-gradient(135deg, rgba(79, 140, 255, 0.1), rgba(37, 99, 235, 0.04));
  border-left-color: var(--app-primary, #4f8cff);
  color: #1d4ed8;
}

.conv-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.08);
  flex-shrink: 0;
  color: inherit;
}

.conv-item--active .conv-item__icon {
  background: rgba(79, 140, 255, 0.12);
}

.conv-item__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item__title {
  font-size: 0.84rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: inherit;
}

.conv-item__time {
  font-size: 0.7rem;
  color: #94a3b8;
}

.conv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 16px;
  color: #94a3b8;
  font-size: 0.82rem;
}

.conv-empty__icon {
  opacity: 0.4;
}

/* ===== Main chat ===== */
.chat-main {
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--app-radius-lg, 24px);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--app-shadow-soft, 0 10px 30px rgba(15,23,42,0.1));
  backdrop-filter: blur(16px);
  overflow: hidden;
}

.chat-main__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.chat-main__header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #475569;
}

.chat-main__title {
  display: block;
  font-size: 0.95rem;
  font-weight: 700;
  color: #0f172a;
}

.chat-main__subtitle {
  display: block;
  font-size: 0.72rem;
  color: #94a3b8;
  font-weight: 500;
}

.online-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--app-success, #22c55e);
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.4);
  animation: pulse 2s ease infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ===== Message area ===== */
.message-area {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px;
  min-height: 300px;
}

.empty-chat {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
}

.empty-chat__icon-ring {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.06);
  border: 1px dashed rgba(148, 163, 184, 0.2);
  color: #94a3b8;
}

.empty-chat__title {
  font-size: 1rem;
  font-weight: 700;
  color: #475569;
}

.empty-chat__hint {
  font-size: 0.82rem;
  color: #94a3b8;
  max-width: 360px;
  text-align: center;
  line-height: 1.6;
}

/* ===== Timestamp separator ===== */
.timestamp-separator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0;
}

.timestamp-separator span {
  font-size: 0.7rem;
  font-weight: 500;
  color: #94a3b8;
  padding: 2px 12px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.08);
}

/* ===== Message rows ===== */
.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.message-row.user {
  flex-direction: row-reverse;
}

.message-row.assistant {
  flex-direction: row;
}

/* ===== Avatars ===== */
.msg-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 12px;
  flex-shrink: 0;
}

.msg-avatar.user {
  background: linear-gradient(135deg, var(--app-primary, #4f8cff), var(--app-primary-strong, #2563eb));
  color: #fff;
}

.msg-avatar.assistant {
  background: rgba(148, 163, 184, 0.1);
  color: #475569;
  border: 1px solid rgba(148, 163, 184, 0.15);
}

/* ===== Chat bubbles (scoped overrides) ===== */
.chat-bubble {
  max-width: min(76%, 700px);
  padding: 14px 18px;
  border-radius: 18px;
  line-height: 1.75;
  font-size: 0.9rem;
  word-break: break-word;
}

.chat-bubble.user {
  background: linear-gradient(135deg, #2563eb, #4f8cff);
  color: #eff6ff;
  border-bottom-right-radius: 6px;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.18);
}

.chat-bubble.assistant {
  background: rgba(255, 255, 255, 0.92);
  color: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-bottom-left-radius: 6px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
  backdrop-filter: blur(12px);
}

.chat-bubble.assistant p {
  margin: 0 0 10px 0;
}

.chat-bubble.assistant p:last-child {
  margin-bottom: 0;
}

/* ===== AI structured response ===== */
.ai-structured {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-analysis {
  line-height: 1.8;
}

/* Tags */
.ai-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ai-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.ai-tag--critical,
.ai-tag--high {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.ai-tag--medium,
.ai-tag--warning {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.ai-tag--low {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.ai-tag--info {
  background: rgba(79, 140, 255, 0.1);
  color: #2563eb;
}

/* MITRE card */
.mitre-card {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(79, 140, 255, 0.05);
  border: 1px solid rgba(79, 140, 255, 0.12);
}

.mitre-card__header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2563eb;
  margin-bottom: 10px;
}

.mitre-card__field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
}

.mitre-card__field:not(:last-child) {
  border-bottom: 1px solid rgba(79, 140, 255, 0.08);
}

.mitre-card__label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #94a3b8;
}

.mitre-card__value {
  font-size: 0.84rem;
  font-weight: 600;
  color: #0f172a;
}

/* Rationale */
.rationale-block {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(241, 245, 249, 0.8);
  border-left: 3px solid #94a3b8;
}

.rationale-block__label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #475569;
  margin-bottom: 6px;
}

.rationale-block p {
  font-size: 0.84rem;
  color: #475569;
  line-height: 1.7;
  margin: 0;
}

/* Recommendation card */
.recommendation-card {
  display: flex;
  gap: 14px;
  padding: 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.06), rgba(34, 197, 94, 0.02));
  border: 1px solid rgba(34, 197, 94, 0.16);
}

.recommendation-card__icon {
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
  flex-shrink: 0;
}

.recommendation-card__body {
  min-width: 0;
}

.recommendation-card__title {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #16a34a;
  margin-bottom: 6px;
}

.recommendation-card__body p {
  font-size: 0.84rem;
  color: #475569;
  line-height: 1.7;
  margin: 0;
}

/* ===== Typing indicator ===== */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
}

.typing-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #94a3b8;
  animation: typingBounce 1.2s ease infinite;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typingBounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

/* ===== Input surface ===== */
.input-surface {
  padding: 16px 24px 20px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
  background: rgba(248, 250, 252, 0.6);
  backdrop-filter: blur(16px);
}

.input-wrapper {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  border: 1.5px solid rgba(148, 163, 184, 0.18);
  transition: border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.input-wrapper--focused {
  border-color: rgba(79, 140, 255, 0.4);
  box-shadow: 0 0 0 3px rgba(79, 140, 255, 0.08);
}

.input-wrapper :deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  border-radius: 0 !important;
  padding: 14px 16px !important;
  background: transparent !important;
  font-size: 0.88rem;
}

.char-progress {
  height: 2px;
  background: rgba(148, 163, 184, 0.08);
}

.char-progress__bar {
  height: 100%;
  background: var(--app-primary, #4f8cff);
  transition: width 0.2s ease;
  border-radius: 0 999px 999px 0;
}

.char-progress__bar--warn {
  background: var(--app-danger, #ef4444);
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.input-hint {
  font-size: 0.72rem;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 4px;
}

.input-hint kbd {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0 6px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.8);
  font-size: 0.68rem;
  font-weight: 600;
  color: #475569;
  box-shadow: inset 0 -1px 0 rgba(148, 163, 184, 0.1);
}

.send-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--app-primary, #4f8cff), var(--app-primary-strong, #2563eb));
  color: #fff;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.22);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.send-button:hover:not(:disabled) {
  box-shadow: 0 10px 28px rgba(37, 99, 235, 0.3);
  transform: translateY(-1px);
}

.send-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.send-button__loading {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 999px;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
