<template>
  <section class="alerts-panel">
    <div class="panel-header">
      <h3 class="panel-title">最近告警</h3>
      <a class="view-all-link" @click.prevent="$emit('view-all')">查看全部</a>
    </div>
    <div class="alert-list">
      <div
        v-for="alert in alerts"
        :key="alert.id"
        class="alert-item"
      >
        <div class="alert-item__bar" :style="{ background: severityColor(alert.severity) }"></div>
        <div class="alert-item__body">
          <div class="alert-item__top">
            <span class="alert-item__id">#{{ alert.id }}</span>
            <span class="alert-item__title">{{ alert.title }}</span>
          </div>
          <div class="alert-item__meta">
            <span class="alert-chip" :style="chipStyle(alert.severity)">
              {{ alert.severity }}
            </span>
            <span class="alert-chip alert-chip--source">{{ alert.source }}</span>
            <span v-if="alert.src_ip" class="alert-chip alert-chip--ip">{{ alert.src_ip }}</span>
            <span
              class="alert-chip"
              :class="alert.status === 'open' ? 'alert-chip--open' : 'alert-chip--closed'"
            >
              {{ alert.status }}
            </span>
            <span class="alert-item__time">{{ alert.created_at }}</span>
          </div>
        </div>
      </div>
      <div v-if="!alerts.length" class="alert-empty">
        <p>暂无告警数据</p>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  alerts: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['view-all'])

function severityColor(severity) {
  const map = { critical: '#ef4444', high: '#ef4444', medium: '#f59e0b', low: '#22c55e', info: '#4f8cff' }
  return map[severity] || '#94a3b8'
}

function chipStyle(severity) {
  const c = severityColor(severity)
  return { background: c + '14', color: c, borderColor: c + '30' }
}
</script>

<style scoped>
.alerts-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.panel-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}
.view-all-link {
  color: var(--accent);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
}
.view-all-link:hover {
  text-decoration: underline;
}

/* Alert List */
.alert-list {
  padding: 8px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.alert-item {
  display: flex;
  align-items: stretch;
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  border: 1px solid var(--border);
  overflow: hidden;
  transition: background 0.15s ease;
}
.alert-item:hover {
  background: var(--bg-hover);
}
.alert-item__bar {
  width: 3px;
  flex-shrink: 0;
}
.alert-item__body {
  flex: 1;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.alert-item__top {
  display: flex;
  align-items: center;
  gap: 10px;
}
.alert-item__id {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-muted);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.alert-item__title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.alert-item__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.alert-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  border: 1px solid transparent;
  text-transform: capitalize;
}
.alert-chip--source {
  background: rgba(59, 130, 246, 0.08);
  color: #2563eb;
  border-color: rgba(59, 130, 246, 0.18);
}
.alert-chip--ip {
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-secondary);
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 0.7rem;
  letter-spacing: -0.02em;
}
.alert-chip--open {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.2);
}
.alert-chip--closed {
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-secondary);
  border-color: rgba(148, 163, 184, 0.18);
}
.alert-item__time {
  margin-left: auto;
  font-size: 0.72rem;
  color: var(--text-muted);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.alert-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 24px;
  color: var(--text-muted);
  font-size: 0.88rem;
}
</style>
