<template>
  <header class="app-header">
    <div class="header-left">
      <div class="header-title">{{ title }}</div>
      <div class="header-subtitle">{{ subtitle }}</div>
    </div>
    <div class="header-right">
      <el-tooltip :content="backendTip" placement="bottom">
        <span class="status-dot" :class="systemHealth.backend"></span>
      </el-tooltip>
      <el-tooltip :content="agentTip" placement="bottom">
        <span class="status-dot" :class="systemHealth.agent"></span>
      </el-tooltip>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  systemHealth: {
    type: Object,
    default: () => ({ backend: 'checking', agent: 'checking' }),
  },
})

function label(status) {
  if (status === 'healthy') return '正常'
  if (status === 'degraded') return '异常'
  return '检查中'
}

const backendTip = computed(() => `Backend: ${label(props.systemHealth.backend)}`)
const agentTip = computed(() => `Agent: ${label(props.systemHealth.agent)}`)
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.header-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.header-subtitle {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  cursor: default;
}

.status-dot.healthy {
  background: var(--success);
}

.status-dot.degraded {
  background: var(--danger);
}
</style>
