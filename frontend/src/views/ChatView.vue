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
      <el-card shadow="hover" class="chat-history-card">
        <template #header>
          <div class="section-title">
            <span>对话历史</span>
            <el-button text type="primary" size="small" @click="newConversation">
              <el-icon><Plus /></el-icon> 新建
            </el-button>
          </div>
        </template>
        <div class="chat-history-list">
          <div
            v-for="(conv, idx) in conversations"
            :key="idx"
            :class="['conv-item', { active: currentConvIndex === idx }]"
            @click="switchConversation(idx)"
          >
            <el-icon><ChatDotRound /></el-icon>
            <span class="conv-title">{{ conv.title || `对话 ${idx + 1}` }}</span>
          </div>
          <el-empty v-if="conversations.length === 0" description="暂无对话" :image-size="60" />
        </div>
      </el-card>

      <el-card shadow="hover" class="chat-main-card">
        <template #header>
          <div class="section-title">
            <span>AI 安全分析助手</span>
            <small>Structured Security Reasoning</small>
          </div>
        </template>

        <div ref="messageArea" class="message-area">
          <div v-if="currentMessages.length === 0" class="empty-chat">
            <el-icon :size="48" color="#94a3b8"><ChatDotRound /></el-icon>
            <p>开始与 AI 安全助手对话</p>
          </div>

          <div
            v-for="(msg, idx) in currentMessages"
            :key="idx"
            :class="['message-row', msg.role]"
          >
            <div :class="['chat-bubble', msg.role]">
              <template v-if="msg.role === 'assistant'">
                <template v-if="msg._parsed">
                  <div class="ai-structured">
                    <div class="ai-analysis" v-html="renderMarkdown(msg._parsed.analysis || '')"></div>

                    <div class="ai-tags" v-if="msg._parsed.risk_level || msg._parsed.confidence">
                      <el-tag
                        v-if="msg._parsed.risk_level"
                        :type="getRiskTagType(msg._parsed.risk_level)"
                        size="small"
                      >风险等级: {{ msg._parsed.risk_level }}</el-tag>
                      <el-tag v-if="msg._parsed.confidence" type="info" size="small">
                        置信度: {{ msg._parsed.confidence }}
                      </el-tag>
                      <el-tag v-if="msg._parsed.action_type" type="warning" size="small">
                        动作: {{ msg._parsed.action_type }}
                      </el-tag>
                    </div>

                    <div class="ai-fields" v-if="msg._parsed.mitre_tactic || msg._parsed.mitre_technique">
                      <div v-if="msg._parsed.mitre_tactic" class="ai-field">
                        <span class="ai-field-label">MITRE 战术:</span>
                        <span>{{ msg._parsed.mitre_tactic }}</span>
                      </div>
                      <div v-if="msg._parsed.mitre_technique" class="ai-field">
                        <span class="ai-field-label">MITRE 技术:</span>
                        <span>{{ msg._parsed.mitre_technique }}</span>
                      </div>
                    </div>

                    <div v-if="msg._parsed.rationale" class="ai-field standalone-field">
                      <span class="ai-field-label">依据:</span>
                      <span>{{ msg._parsed.rationale }}</span>
                    </div>

                    <el-alert
                      v-if="msg._parsed.recommendation"
                      :title="'建议'"
                      type="success"
                      :description="msg._parsed.recommendation"
                      :closable="false"
                      show-icon
                    />
                  </div>
                </template>
                <div v-else v-html="renderMarkdown(msg.content)"></div>
              </template>
              <span v-else>{{ msg.content }}</span>
            </div>
          </div>

          <div v-if="sending" class="message-row assistant">
            <div class="chat-bubble assistant">
              <el-icon class="is-loading"><Loading /></el-icon> 正在思考...
            </div>
          </div>
        </div>

        <div class="input-area">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="3"
            placeholder="输入安全分析问题..."
            resize="none"
            @keydown.enter.ctrl="handleSend"
            @keydown.enter.meta="handleSend"
          />
          <div class="input-hint">按 <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> 发送，单独 Enter 换行</div>
          <el-button
            type="primary"
            :loading="sending"
            :disabled="!inputText.trim()"
            @click="handleSend"
            class="send-btn"
          >
            <el-icon><Promotion /></el-icon> 发送
          </el-button>
        </div>
      </el-card>
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
.chat-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 20px;
  min-height: calc(100vh - 250px);
}

.chat-history-card,
.chat-main-card {
  display: flex;
  flex-direction: column;
}

.chat-history-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.message-area {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-right: 6px;
}

.empty-chat {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
}

.empty-chat p {
  margin-top: 14px;
}

.message-row {
  display: flex;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 18px;
  margin-top: 18px;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.input-hint {
  color: #64748b;
  font-size: 0.78rem;
}

.send-btn {
  align-self: flex-end;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 14px;
  cursor: pointer;
  color: #475569;
  transition: all 0.2s ease;
}

.conv-item:hover {
  background: rgba(79, 140, 255, 0.08);
}

.conv-item.active {
  background: linear-gradient(135deg, rgba(79, 140, 255, 0.14), rgba(37, 99, 235, 0.06));
  color: #1d4ed8;
}

.conv-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-structured {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-analysis {
  line-height: 1.75;
}

.ai-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ai-fields,
.standalone-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  background: rgba(241, 245, 249, 0.9);
  border-radius: 12px;
  font-size: 0.84rem;
}

.ai-field {
  color: #475569;
}

.ai-field-label {
  font-weight: 700;
  color: #0f172a;
  margin-right: 6px;
}

@media (max-width: 1024px) {
  .chat-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
