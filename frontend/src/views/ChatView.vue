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
            <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)"></div>
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
        />
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
import { marked } from 'marked'
import { chatWithAI } from '../api'

const conversations = ref([{ title: '新对话', messages: [] }])
const currentConvIndex = ref(0)
const inputText = ref('')
const sending = ref(false)
const messageArea = ref(null)

const currentMessages = computed(() => {
  return conversations.value[currentConvIndex.value]?.messages || []
})

function renderMarkdown(text) {
  try {
    return marked.parse(text || '')
  } catch {
    return text
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
</style>
