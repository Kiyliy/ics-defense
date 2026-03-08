<template>
  <aside class="conv-sidebar">
    <button class="new-chat-btn" @click="$emit('new')">
      <svg viewBox="0 0 16 16" width="16" height="16"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>
      新建对话
    </button>

    <div class="conv-list">
      <div
        v-for="(conv, idx) in conversations"
        :key="idx"
        :class="['conv-item', { 'conv-item--active': currentIndex === idx }]"
        @click="$emit('select', idx)"
      >
        <div class="conv-item__icon">
          <svg viewBox="0 0 16 16" width="16" height="16"><path d="M2 3a2 2 0 012-2h8a2 2 0 012 2v6a2 2 0 01-2 2H6l-3 3V11a2 2 0 01-1-2V3z" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
        </div>
        <div class="conv-item__body">
          <span class="conv-item__title">{{ conv.title || `对话 ${idx + 1}` }}</span>
          <span class="conv-item__count" v-if="conv.messages && conv.messages.length">
            {{ conv.messages.length }} 条消息
          </span>
        </div>
      </div>
      <div v-if="conversations.length === 0" class="conv-empty">
        <svg viewBox="0 0 16 16" width="32" height="32"><path d="M2 3a2 2 0 012-2h8a2 2 0 012 2v6a2 2 0 01-2 2H6l-3 3V11a2 2 0 01-1-2V3z" stroke="var(--text-muted)" stroke-width="1.5" fill="none"/></svg>
        <span>暂无对话</span>
      </div>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  conversations: { type: Array, required: true },
  currentIndex: { type: Number, required: true },
})

defineEmits(['select', 'new'])
</script>

<style scoped>
.conv-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
  overflow: hidden;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s var(--ease);
}

.new-chat-btn:hover {
  background: var(--bg-hover);
}

.conv-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  flex: 1;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.15s var(--ease);
  color: var(--text-secondary);
}

.conv-item:hover {
  background: var(--bg-hover);
}

.conv-item--active {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.conv-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  color: inherit;
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

.conv-item__count {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.conv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--text-muted);
  font-size: 0.82rem;
}
</style>
