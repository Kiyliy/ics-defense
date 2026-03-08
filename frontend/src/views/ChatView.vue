<template>
  <div style="display: flex; height: calc(100vh - 120px); gap: 16px">
    <!-- 左侧对话历史 -->
    <el-card shadow="hover" style="width: 260px; flex-shrink: 0; display: flex; flex-direction: column">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">对话历史</span>
          <el-button text type="primary" size="small" @click="newConversation">
            <el-icon><Plus /></el-icon> 新建
          </el-button>
        </div>
      </template>
      <div style="flex: 1; overflow-y: auto">
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

    <!-- 右侧聊天窗口 -->
    <el-card shadow="hover" style="flex: 1; display: flex; flex-direction: column; overflow: hidden">
      <template #header>
        <span style="font-weight: 600">AI 安全分析助手</span>
      </template>

      <!-- 消息区域 -->
      <div ref="messageArea" class="message-area">
        <div v-if="currentMessages.length === 0" class="empty-chat">
          <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
          <p style="color: #909399; margin-top: 12px">开始与 AI 安全助手对话</p>
        </div>

        <div
          v-for="(msg, idx) in currentMessages"
          :key="idx"
          :class="['message-row', msg.role]"
        >
          <div :class="['chat-bubble', msg.role]">
            <template v-if="msg.role === 'assistant'">
              <!-- Structured AI response -->
              <template v-if="parseAIResponse(msg.content)">
                <div class="ai-structured">
                  <div class="ai-analysis" v-html="renderMarkdown(parseAIResponse(msg.content).analysis || '')"></div>

                  <div class="ai-tags" v-if="parseAIResponse(msg.content).risk_level || parseAIResponse(msg.content).confidence">
                    <el-tag
                      v-if="parseAIResponse(msg.content).risk_level"
                      :type="riskTagType(parseAIResponse(msg.content).risk_level)"
                      size="small"
                    >风险等级: {{ parseAIResponse(msg.content).risk_level }}</el-tag>
                    <el-tag
                      v-if="parseAIResponse(msg.content).confidence"
                      type="info"
                      size="small"
                    >置信度: {{ parseAIResponse(msg.content).confidence }}</el-tag>
                    <el-tag
                      v-if="parseAIResponse(msg.content).action_type"
                      type="warning"
                      size="small"
                    >动作: {{ parseAIResponse(msg.content).action_type }}</el-tag>
                  </div>

                  <div class="ai-fields" v-if="parseAIResponse(msg.content).mitre_tactic || parseAIResponse(msg.content).mitre_technique">
                    <div v-if="parseAIResponse(msg.content).mitre_tactic" class="ai-field">
                      <span class="ai-field-label">MITRE 战术:</span>
                      <span>{{ parseAIResponse(msg.content).mitre_tactic }}</span>
                    </div>
                    <div v-if="parseAIResponse(msg.content).mitre_technique" class="ai-field">
                      <span class="ai-field-label">MITRE 技术:</span>
                      <span>{{ parseAIResponse(msg.content).mitre_technique }}</span>
                    </div>
                  </div>

                  <div v-if="parseAIResponse(msg.content).rationale" class="ai-field">
                    <span class="ai-field-label">依据:</span>
                    <span>{{ parseAIResponse(msg.content).rationale }}</span>
                  </div>

                  <el-alert
                    v-if="parseAIResponse(msg.content).recommendation"
                    :title="'建议'"
                    type="success"
                    :description="parseAIResponse(msg.content).recommendation"
                    :closable="false"
                    show-icon
                    style="margin-top: 8px"
                  />
                </div>
              </template>
              <!-- Plain text / markdown response -->
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

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
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
          style="margin-top: 8px; align-self: flex-end"
        >
          <el-icon><Promotion /></el-icon> 发送
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { chatWithAI } from '../api'
import { renderMarkdownSafe } from '../api/markdown.js'

const conversations = ref([{ title: '新对话', messages: [] }])
const currentConvIndex = ref(0)
const inputText = ref('')
const sending = ref(false)
const messageArea = ref(null)

const currentMessages = computed(() => {
  return conversations.value[currentConvIndex.value]?.messages || []
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

function riskTagType(level) {
  if (!level) return 'info'
  const l = level.toLowerCase()
  if (l === 'high' || l === '高') return 'danger'
  if (l === 'medium' || l === '中') return 'warning'
  if (l === 'low' || l === '低') return 'success'
  return 'info'
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
.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
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
  border-top: 1px solid #ebeef5;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
}

.input-hint {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

kbd {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 0 4px;
  background: #f5f7fa;
  font-family: inherit;
  font-size: 12px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
  transition: background 0.2s;
}

.conv-item:hover {
  background: #f5f7fa;
}

.conv-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.conv-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-structured {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-analysis {
  line-height: 1.6;
}

.ai-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.ai-fields {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
}

.ai-field {
  font-size: 13px;
  color: #606266;
}

.ai-field-label {
  font-weight: 600;
  color: #303133;
  margin-right: 6px;
}
</style>
