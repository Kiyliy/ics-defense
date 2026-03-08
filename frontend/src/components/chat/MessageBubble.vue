<template>
  <div :class="['message-row', message.role]">
    <!-- Avatar -->
    <div :class="['msg-avatar', message.role]">
      <svg v-if="message.role === 'user'" viewBox="0 0 16 16" width="14" height="14"><circle cx="8" cy="6" r="3" fill="currentColor"/><path d="M2 14a6 6 0 0112 0" fill="currentColor"/></svg>
      <svg v-else viewBox="0 0 16 16" width="14" height="14"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M5 8h6M8 5v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
    </div>

    <div :class="['chat-bubble', message.role]">
      <template v-if="message.role === 'assistant'">
        <StructuredResponse v-if="message._parsed" :parsed="message._parsed" />
        <div v-else v-html="renderMarkdown(message.content)"></div>
      </template>
      <span v-else>{{ message.content }}</span>
    </div>
  </div>
</template>

<script setup>
import StructuredResponse from './StructuredResponse.vue'

defineProps({
  message: { type: Object, required: true },
  renderMarkdown: { type: Function, required: true },
})
</script>

<style scoped>
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

/* Avatars */
.msg-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
}

.msg-avatar.user {
  background: var(--text-primary);
  color: #fff;
}

.msg-avatar.assistant {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

/* Bubbles */
.chat-bubble {
  max-width: min(76%, 700px);
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.75;
  font-size: 0.9rem;
  word-break: break-word;
}

.chat-bubble.user {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-bottom-right-radius: 4px;
}

.chat-bubble.assistant {
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.chat-bubble.assistant :deep(p) {
  margin: 0 0 10px 0;
}

.chat-bubble.assistant :deep(p:last-child) {
  margin-bottom: 0;
}
</style>
