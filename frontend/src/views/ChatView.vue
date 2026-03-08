<template>
  <div>
    <h1 class="page-title">AI 对话</h1>
    <p class="page-subtitle">结构化安全问答、MITRE 映射与行动建议</p>

    <div class="chat-layout">
      <ConversationList
        :conversations="conversations"
        :current-index="currentConvIndex"
        @select="switchConversation"
        @new="newConversation"
      />

      <div class="chat-main">
        <!-- Messages area -->
        <div ref="messageArea" class="message-area">
          <!-- Empty state -->
          <div v-if="currentMessages.length === 0" class="empty-chat">
            <div class="empty-chat__icon-ring">
              <svg viewBox="0 0 48 48" width="48" height="48"><circle cx="24" cy="24" r="20" stroke="var(--text-muted)" stroke-width="1.5" fill="none" stroke-dasharray="4 3"/><path d="M16 20a8 8 0 0116 0v2a8 8 0 01-16 0v-2z" stroke="var(--text-muted)" stroke-width="1.5" fill="none"/><path d="M20 30l-2 6M28 30l2 6" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
            </div>
            <p class="empty-chat__title">开始与 AI 安全助手对话</p>
            <p class="empty-chat__hint">输入安全分析问题，获取结构化分析、MITRE 映射与行动建议</p>
          </div>

          <!-- Messages -->
          <template v-for="(msg, idx) in currentMessages" :key="idx">
            <div v-if="idx === 0 || shouldShowTimestamp(idx)" class="ts-sep">
              <span>{{ getMessageTime(msg) }}</span>
            </div>
            <MessageBubble :message="msg" :render-markdown="renderMarkdown" />
          </template>

          <!-- Typing indicator -->
          <div v-if="sending" class="typing-row">
            <div class="msg-avatar assistant">
              <svg viewBox="0 0 16 16" width="14" height="14"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M5 8h6M8 5v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
            </div>
            <div class="typing-bubble">
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
            </div>
          </div>
        </div>

        <ChatInput
          v-model="inputText"
          :sending="sending"
          :max-chars="maxChars"
          @send="handleSend"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import ConversationList from '../components/chat/ConversationList.vue'
import MessageBubble from '../components/chat/MessageBubble.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import { useChat } from '../composables/useChat.js'

const {
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
} = useChat()
</script>

<style scoped>
.chat-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
  min-height: calc(100vh - 180px);
}

@media (max-width: 1024px) {
  .chat-layout {
    grid-template-columns: 1fr;
  }
}

.chat-main {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.message-area {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px;
  min-height: 300px;
}

/* Empty state */
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
  border-radius: 50%;
  background: var(--bg-hover);
  border: 1px dashed var(--border);
}

.empty-chat__title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.empty-chat__hint {
  font-size: 0.82rem;
  color: var(--text-muted);
  max-width: 360px;
  text-align: center;
  line-height: 1.6;
}

/* Timestamp separator */
.ts-sep {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0;
}

.ts-sep span {
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--text-muted);
  padding: 2px 12px;
  border-radius: 999px;
  background: var(--bg-hover);
}

/* Typing indicator */
.typing-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.typing-row .msg-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-hover);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.typing-bubble {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 14px 18px;
  border-radius: 16px;
  border-bottom-left-radius: 4px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
}

.typing-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: typingBounce 1.2s ease infinite;
}

.typing-dot:nth-child(2) { animation-delay: 0.15s; }
.typing-dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}
</style>
