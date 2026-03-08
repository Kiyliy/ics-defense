<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="告警详情"
    width="720px"
    class="alert-detail-dialog"
    :append-to-body="true"
  >
    <div class="detail-content" v-if="detail">
      <!-- Section: 基本信息 -->
      <div class="detail-section">
        <h4 class="detail-section-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          基本信息
        </h4>
        <div class="detail-grid">
          <div class="detail-field">
            <span class="detail-field-label">ID</span>
            <span class="detail-field-value">#{{ detail.id }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-field-label">来源</span>
            <span class="source-chip">{{ detail.source?.toUpperCase() }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-field-label">等级</span>
            <div class="severity-cell">
              <span class="severity-dot" :class="'severity-dot--' + detail.severity"></span>
              <span class="severity-text" :class="'severity-text--' + detail.severity">{{ detail.severity }}</span>
            </div>
          </div>
          <div class="detail-field">
            <span class="detail-field-label">状态</span>
            <span class="status-pill" :class="'status-pill--' + detail.status">{{ detail.status }}</span>
          </div>
          <div class="detail-field detail-field--full">
            <span class="detail-field-label">标题</span>
            <span class="detail-field-value detail-field-value--title">{{ detail.title }}</span>
          </div>
          <div class="detail-field detail-field--full">
            <span class="detail-field-label">时间</span>
            <span class="detail-field-value detail-field-value--muted">{{ detail.created_at }}</span>
          </div>
        </div>
      </div>

      <!-- Section: 网络信息 -->
      <div class="detail-section">
        <h4 class="detail-section-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M7 2v20"/><path d="M17 2v20"/><path d="M2 12h20"/><path d="M2 7h5"/><path d="M2 17h5"/><path d="M17 7h5"/><path d="M17 17h5"/></svg>
          网络信息
        </h4>
        <div class="detail-grid">
          <div class="detail-field">
            <span class="detail-field-label">源 IP</span>
            <span class="detail-field-value cell-ip">{{ detail.src_ip || '-' }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-field-label">目标 IP</span>
            <span class="detail-field-value cell-ip">{{ detail.dst_ip || '-' }}</span>
          </div>
        </div>
      </div>

      <!-- Section: 原始数据 -->
      <div class="detail-section">
        <h4 class="detail-section-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          原始数据
        </h4>
        <pre class="detail-code-block">{{ JSON.stringify(detail.raw_data || detail, null, 2) }}</pre>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  detail: { type: Object, default: null }
})

defineEmits(['update:visible'])
</script>

<style scoped>
.detail-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border, rgba(0,0,0,0.08));
}

.detail-section-title svg {
  color: var(--accent, #3b82f6);
  flex-shrink: 0;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}

.detail-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-field--full {
  grid-column: 1 / -1;
}

.detail-field-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted, #9ca3af);
}

.detail-field-value {
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--text-primary, #0a0a0a);
}

.detail-field-value--title {
  font-weight: 600;
  line-height: 1.5;
}

.detail-field-value--muted {
  color: var(--text-secondary, #6b7280);
  font-size: 0.84rem;
}

.severity-cell { display: inline-flex; align-items: center; gap: 8px; }
.severity-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.severity-dot--critical { background: #ef4444; }
.severity-dot--high { background: #f97316; }
.severity-dot--medium { background: #f59e0b; }
.severity-dot--low { background: #22c55e; }
.severity-text { font-size: 0.82rem; font-weight: 600; text-transform: capitalize; }
.severity-text--critical { color: #dc2626; }
.severity-text--high { color: #ea580c; }
.severity-text--medium { color: #d97706; }
.severity-text--low { color: #16a34a; }

.source-chip {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: var(--radius-md, 8px);
  background: rgba(59, 130, 246, 0.08);
  color: var(--accent, #3b82f6);
  font-size: 0.78rem;
  font-weight: 600;
}

.status-pill {
  display: inline-flex;
  padding: 4px 12px;
  border-radius: var(--radius-full, 999px);
  font-size: 0.76rem;
  font-weight: 600;
  text-transform: capitalize;
}

.status-pill--open { background: rgba(239, 68, 68, 0.1); color: #dc2626; }
.status-pill--analyzing { background: rgba(245, 158, 11, 0.1); color: #d97706; }
.status-pill--analyzed { background: rgba(59, 130, 246, 0.1); color: #2563eb; }
.status-pill--resolved { background: rgba(34, 197, 94, 0.1); color: #16a34a; }

.cell-ip {
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
  color: var(--text-secondary, #6b7280);
}

.detail-code-block {
  padding: 16px 20px;
  border-radius: var(--radius-lg, 12px);
  background: #0f172a;
  color: #93c5fd;
  font-family: var(--font-mono, monospace);
  font-size: 0.8rem;
  line-height: 1.7;
  overflow: auto;
  max-height: 320px;
  white-space: pre-wrap;
  word-break: break-all;
}

@media (max-width: 768px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
