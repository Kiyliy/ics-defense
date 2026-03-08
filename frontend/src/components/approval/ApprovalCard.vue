<template>
  <div class="approval-card" :class="'approval-card--' + item.status">
    <!-- Left Status Bar -->
    <div class="card-status-bar" :class="'card-status-bar--' + item.status"></div>

    <div class="card-body">
      <!-- Card Header -->
      <div class="card-header">
        <div class="card-header-left">
          <h4 class="card-tool-name">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
            {{ item.tool_name }}
          </h4>
          <span class="card-trace-id">{{ item.trace_id }}</span>
        </div>
        <span class="card-status-badge" :class="'card-status-badge--' + item.status">
          {{ statusLabel(item.status) }}
        </span>
      </div>

      <!-- Args Preview -->
      <div class="card-args-section">
        <button
          class="card-args-toggle"
          @click="$emit('toggle-args')"
          :class="{ 'card-args-toggle--open': argsExpanded }"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          <span class="card-args-preview" v-if="!argsExpanded">{{ truncateArgs(item.tool_args) }}</span>
          <span v-else>收起参数</span>
        </button>
        <Transition name="args-expand">
          <pre class="card-args-code" v-if="argsExpanded">{{ formatArgs(item.tool_args) }}</pre>
        </Transition>
      </div>

      <!-- Card Footer -->
      <div class="card-footer">
        <span class="card-time">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          {{ item.created_at }}
        </span>

        <div class="card-actions" v-if="item.status === 'pending'">
          <button class="card-action-btn card-action-btn--approve" @click="$emit('approve', item)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            批准
          </button>
          <button class="card-action-btn card-action-btn--reject" @click="$emit('reject', item)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            拒绝
          </button>
        </div>
        <span class="card-processed" v-else>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          已处理
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  item: { type: Object, required: true },
  argsExpanded: { type: Boolean, default: false }
})

defineEmits(['approve', 'reject', 'toggle-args'])

function statusLabel(status) {
  const map = { pending: '待审批', approved: '已批准', rejected: '已拒绝' }
  return map[status] || status
}

function truncateArgs(args) {
  const str = typeof args === 'string' ? args : JSON.stringify(args)
  return str.length > 60 ? str.slice(0, 60) + '...' : str
}

function formatArgs(args) {
  try {
    const obj = typeof args === 'string' ? JSON.parse(args) : args
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(args)
  }
}
</script>

<style scoped>
.approval-card {
  display: flex;
  border-radius: var(--radius-md, 8px);
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
  overflow: hidden;
  transition: all 0.2s var(--ease, ease);
}

.approval-card:hover {
  border-color: var(--border-strong, rgba(0,0,0,0.15));
}

/* Status Bar (left edge) */
.card-status-bar { width: 4px; flex-shrink: 0; }
.card-status-bar--pending { background: #f59e0b; }
.card-status-bar--approved { background: #16a34a; }
.card-status-bar--rejected { background: #dc2626; }

.card-body {
  flex: 1;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Card Header */
.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.card-header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.card-tool-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
}

.card-tool-name svg {
  color: var(--accent, #3b82f6);
  flex-shrink: 0;
}

.card-trace-id {
  font-family: var(--font-mono, monospace);
  font-size: 0.78rem;
  color: var(--text-muted, #9ca3af);
  word-break: break-all;
}

.card-status-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--radius-full, 999px);
  font-size: 0.76rem;
  font-weight: 600;
  flex-shrink: 0;
}

.card-status-badge--pending { background: rgba(245, 158, 11, 0.1); color: #d97706; }
.card-status-badge--approved { background: rgba(34, 197, 94, 0.1); color: #16a34a; }
.card-status-badge--rejected { background: rgba(239, 68, 68, 0.1); color: #dc2626; }

/* Args Section */
.card-args-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-args-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  border-radius: var(--radius-md, 8px);
  background: rgba(59, 130, 246, 0.06);
  color: var(--text-secondary, #6b7280);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s var(--ease, ease);
  text-align: left;
  width: fit-content;
  max-width: 100%;
}

.card-args-toggle svg { color: var(--accent, #3b82f6); flex-shrink: 0; }
.card-args-toggle:hover { background: rgba(59, 130, 246, 0.12); color: #1d4ed8; }
.card-args-toggle--open { background: rgba(59, 130, 246, 0.1); color: #2563eb; }

.card-args-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono, monospace);
  font-size: 0.78rem;
}

.card-args-code {
  padding: 14px 18px;
  border-radius: var(--radius-lg, 12px);
  background: #0f172a;
  color: #93c5fd;
  font-family: var(--font-mono, monospace);
  font-size: 0.78rem;
  line-height: 1.7;
  overflow: auto;
  max-height: 240px;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

/* Args expand transition */
.args-expand-enter-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.args-expand-leave-active { transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
.args-expand-enter-from { opacity: 0; max-height: 0; transform: translateY(-8px); }
.args-expand-leave-to { opacity: 0; max-height: 0; }

/* Card Footer */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border, rgba(0,0,0,0.08));
}

.card-time {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.8rem;
  color: var(--text-muted, #9ca3af);
}

.card-actions {
  display: flex;
  gap: 8px;
}

.card-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius-md, 8px);
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s var(--ease, ease);
}

.card-action-btn--approve {
  background: #0a0a0a;
  color: #fff;
}

.card-action-btn--approve:hover {
  background: #1a1a1a;
}

.card-action-btn--reject {
  background: transparent;
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.card-action-btn--reject:hover {
  background: rgba(239, 68, 68, 0.06);
}

.card-processed {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.8rem;
  color: var(--text-muted, #9ca3af);
}

@media (max-width: 768px) {
  .card-header { flex-direction: column; }
  .card-footer { flex-direction: column; align-items: flex-start; gap: 12px; }
  .card-actions { width: 100%; }
  .card-action-btn { flex: 1; justify-content: center; }
}
</style>
