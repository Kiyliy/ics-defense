<template>
  <div class="event-node" :class="'event-' + category">
    <div class="event-rail">
      <div class="event-dot-outer">
        <div class="event-dot-inner"></div>
      </div>
      <div v-if="!isLast" class="event-connector"></div>
    </div>
    <div class="event-content">
      <div class="event-header">
        <span class="event-type-badge" :class="'badge-' + category">
          {{ label }}
        </span>
        <span class="event-time">{{ time }}</span>
      </div>
      <div class="event-body">
        <!-- LLM 回复内容单独展示 -->
        <div v-if="llmContent" class="llm-content-block">
          <div class="llm-content-label">模型回复</div>
          <div class="llm-content-text">{{ llmContentPreview }}</div>
          <div v-if="llmContent.length > 200" class="llm-content-toggle" @click.stop="showFullLlm = !showFullLlm">
            {{ showFullLlm ? '收起' : '展开全部' }}
          </div>
          <Transition name="fade">
            <div v-if="showFullLlm" class="llm-content-full">{{ llmContent }}</div>
          </Transition>
        </div>
        <div class="event-data-preview" @click.stop="$emit('toggle-detail')">
          <span class="data-text">{{ preview }}</span>
          <span class="expand-hint" v-if="canExpand">
            {{ expanded ? '收起' : '展开' }}
          </span>
        </div>
        <Transition name="fade">
          <pre v-if="expanded" class="event-data-full">{{ fullData }}</pre>
        </Transition>
      </div>
      <div class="event-footer" v-if="event.token_usage">
        <div class="token-bar">
          <div class="token-info">
            <span class="token-label">Token</span>
            <span class="token-value">{{ tokenUsageStr }}</span>
          </div>
          <div class="token-progress" v-if="hasTokens">
            <div class="token-progress-input" :style="{ width: inputPct + '%' }"></div>
            <div class="token-progress-output" :style="{ width: outputPct + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  eventTypeLabel,
  formatEventTime,
  truncateData,
  dataLength,
  formatData,
  parseTokens,
  formatTokenUsage,
  tokenInputPct,
  tokenOutputPct,
} from '../../composables/useAgentLogs.js'

const props = defineProps({
  event: { type: Object, required: true },
  isLast: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
  category: { type: String, default: 'default' },
  maxTokens: { type: Number, default: 1 },
})

defineEmits(['toggle-detail'])

const showFullLlm = ref(false)

const label = computed(() => eventTypeLabel(props.event.event_type))
const time = computed(() => formatEventTime(props.event.created_at))
const preview = computed(() => truncateData(props.event.data))
const canExpand = computed(() => dataLength(props.event.data) > 80)
const fullData = computed(() => formatData(props.event.data))
const tokenUsageStr = computed(() => formatTokenUsage(props.event.token_usage))
const hasTokens = computed(() => !!parseTokens(props.event.token_usage))
const inputPct = computed(() => tokenInputPct(props.event.token_usage, props.maxTokens))
const outputPct = computed(() => tokenOutputPct(props.event.token_usage, props.maxTokens))

// 提取 LLM 回复内容（仅 llm_call / llm_summary_call 事件）
const llmContent = computed(() => {
  const et = props.event.event_type
  if (et !== 'llm_call' && et !== 'llm_summary_call') return ''
  let data = props.event.data
  if (typeof data === 'string') {
    try { data = JSON.parse(data) } catch { return '' }
  }
  return data?.content || ''
})

const llmContentPreview = computed(() => {
  if (!llmContent.value) return ''
  return llmContent.value.length > 200
    ? llmContent.value.slice(0, 200) + '...'
    : llmContent.value
})
</script>

<style scoped>
.event-node {
  display: flex;
  gap: 16px;
  padding-top: 18px;
}

.event-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 22px;
}

.event-dot-outer {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.event-dot-inner {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.event-llm .event-dot-outer { background: rgba(99, 102, 241, 0.12); }
.event-llm .event-dot-inner { background: #6366f1; }
.event-tool .event-dot-outer { background: rgba(245, 158, 11, 0.12); }
.event-tool .event-dot-inner { background: #f59e0b; }
.event-decision .event-dot-outer { background: rgba(34, 197, 94, 0.12); }
.event-decision .event-dot-inner { background: #22c55e; }
.event-error .event-dot-outer { background: rgba(239, 68, 68, 0.12); }
.event-error .event-dot-inner { background: #ef4444; }
.event-default .event-dot-outer { background: rgba(156, 163, 175, 0.12); }
.event-default .event-dot-inner { background: #9ca3af; }

.event-connector {
  width: 2px;
  flex: 1;
  min-height: 16px;
  background: var(--border, rgba(0, 0, 0, 0.08));
  border-radius: 1px;
}

.event-content {
  flex: 1;
  min-width: 0;
  padding-bottom: 8px;
}

.event-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.event-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: var(--radius-md, 8px);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.badge-llm { background: rgba(99, 102, 241, 0.08); color: #6366f1; }
.badge-tool { background: rgba(245, 158, 11, 0.08); color: #b45309; }
.badge-decision { background: rgba(34, 197, 94, 0.08); color: #15803d; }
.badge-error { background: rgba(239, 68, 68, 0.08); color: #dc2626; }
.badge-default { background: rgba(156, 163, 175, 0.08); color: #475569; }

.event-time {
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
  font-family: var(--font-mono, monospace);
}

.event-body {
  margin-bottom: 8px;
}

.event-data-preview {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-md, 8px);
  background: var(--bg-page, #f8f9fa);
  border: 1px solid var(--border, rgba(0, 0, 0, 0.08));
  cursor: pointer;
  transition: border-color 0.2s;
}

.event-data-preview:hover {
  border-color: var(--border-strong, rgba(0, 0, 0, 0.15));
}

.data-text {
  font-size: 0.82rem;
  color: var(--text-secondary, #6b7280);
  line-height: 1.5;
  font-family: var(--font-mono, monospace);
  word-break: break-all;
}

.expand-hint {
  flex-shrink: 0;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--accent, #3b82f6);
}

.event-data-full {
  margin-top: 8px;
  padding: 16px;
  border-radius: var(--radius-md, 8px);
  background: #0f172a;
  color: #dbeafe;
  font-size: 0.78rem;
  line-height: 1.7;
  font-family: var(--font-mono, monospace);
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
}

/* LLM content block */
.llm-content-block {
  margin-bottom: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md, 8px);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.04), rgba(139, 92, 246, 0.06));
  border: 1px solid rgba(99, 102, 241, 0.15);
}

.llm-content-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6366f1;
  margin-bottom: 6px;
}

.llm-content-text {
  font-size: 0.84rem;
  line-height: 1.7;
  color: var(--text-primary, #1e293b);
  white-space: pre-wrap;
  word-break: break-word;
}

.llm-content-toggle {
  margin-top: 6px;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--accent, #3b82f6);
  cursor: pointer;
}

.llm-content-toggle:hover {
  text-decoration: underline;
}

.llm-content-full {
  margin-top: 8px;
  font-size: 0.82rem;
  line-height: 1.7;
  color: var(--text-primary, #1e293b);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Token bar */
.token-bar {
  padding: 8px 14px;
  border-radius: var(--radius-md, 8px);
  background: var(--bg-page, #f8f9fa);
  border: 1px solid var(--border, rgba(0, 0, 0, 0.08));
}

.token-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.token-label {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.token-value {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary, #6b7280);
  font-family: var(--font-mono, monospace);
}

.token-progress {
  display: flex;
  height: 4px;
  border-radius: 2px;
  background: var(--border, rgba(0, 0, 0, 0.08));
  overflow: hidden;
  gap: 1px;
}

.token-progress-input {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, #6366f1, #818cf8);
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.token-progress-output {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
