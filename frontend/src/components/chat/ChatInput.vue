<template>
  <div class="input-surface">
    <div class="input-wrapper" :class="{ 'input-wrapper--focused': focused }">
      <el-input
        :model-value="modelValue"
        type="textarea"
        :rows="3"
        placeholder="输入安全分析问题..."
        resize="none"
        @update:model-value="$emit('update:modelValue', $event)"
        @keydown.enter.ctrl="$emit('send')"
        @keydown.enter.meta="$emit('send')"
        @focus="focused = true"
        @blur="focused = false"
      />
      <!-- Character progress bar -->
      <div class="char-progress">
        <div
          class="char-progress__bar"
          :style="{ width: Math.min(100, (modelValue.length / maxChars) * 100) + '%' }"
          :class="{ 'char-progress__bar--warn': modelValue.length > maxChars * 0.9 }"
        ></div>
      </div>
    </div>
    <div class="input-footer">
      <span class="input-hint">
        <kbd>Ctrl</kbd> + <kbd>Enter</kbd> 发送
      </span>
      <button
        class="send-button"
        :disabled="!modelValue.trim() || sending"
        @click="$emit('send')"
      >
        <svg viewBox="0 0 16 16" width="16" height="16"><path d="M1 8l6-6v4h6a2 2 0 012 2v0a2 2 0 01-2 2H7v4L1 8z" fill="currentColor"/></svg>
        <span>发送</span>
        <span v-if="sending" class="send-button__loading"></span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  modelValue: { type: String, required: true },
  sending: { type: Boolean, default: false },
  maxChars: { type: Number, default: 2000 },
})

defineEmits(['update:modelValue', 'send'])

const focused = ref(false)
</script>

<style scoped>
.input-surface {
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border);
}

.input-wrapper {
  position: relative;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-strong, var(--border));
  transition: border-color 0.2s var(--ease);
}

.input-wrapper--focused {
  border-color: var(--accent);
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
  background: var(--bg-hover);
}

.char-progress__bar {
  height: 100%;
  background: var(--accent);
  transition: width 0.2s ease;
  border-radius: 0 999px 999px 0;
}

.char-progress__bar--warn {
  background: var(--danger, #ef4444);
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.input-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

.input-hint kbd {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.send-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--text-primary);
  color: #fff;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s var(--ease);
}

.send-button:hover:not(:disabled) {
  opacity: 0.85;
}

.send-button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.send-button__loading {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 999px;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
