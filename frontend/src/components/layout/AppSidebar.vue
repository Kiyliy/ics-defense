<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapse }">
    <div class="brand-panel">
      <div class="brand-mark">
        <el-icon :size="18"><Lock /></el-icon>
      </div>
      <span v-show="!isCollapse" class="brand-text">ICS Defense</span>
    </div>

    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      router
      class="sidebar-menu"
    >
      <template v-for="group in groupedItems" :key="group.key">
        <div v-show="!isCollapse" class="nav-group-label">{{ group.label }}</div>
        <el-menu-item
          v-for="item in group.items"
          :key="item.path"
          :index="item.path"
          class="sidebar-menu-item"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </template>
    </el-menu>

    <div class="sidebar-bottom">
      <button class="collapse-toggle" @click="$emit('update:isCollapse', !isCollapse)">
        <el-icon :size="16">
          <Fold v-if="!isCollapse" />
          <Expand v-else />
        </el-icon>
      </button>
      <div v-show="!isCollapse" class="agent-status">
        <span class="status-dot" :class="agentHealthy ? 'healthy' : 'degraded'"></span>
        <span class="status-text">{{ readinessLabel }}</span>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { Fold, Expand } from '@element-plus/icons-vue'

const props = defineProps({
  isCollapse: { type: Boolean, default: false },
  menuItems: { type: Array, default: () => [] },
  activeMenu: { type: String, default: '' },
  readinessLabel: { type: String, default: 'Checking' },
  agentHealthy: { type: Boolean, default: false },
})

defineEmits(['update:isCollapse'])

const groupLabels = {
  overview: '概览',
  security: '安全运营',
  system: '系统',
}

const groupOrder = ['overview', 'security', 'system']

const groupedItems = computed(() => {
  const map = {}
  for (const item of props.menuItems) {
    const g = item.group || 'overview'
    if (!map[g]) map[g] = []
    map[g].push(item)
  }
  return groupOrder
    .filter((key) => map[key]?.length)
    .map((key) => ({
      key,
      label: groupLabels[key] || key,
      items: map[key],
    }))
})
</script>

<style scoped>
.app-sidebar {
  display: flex;
  flex-direction: column;
  width: 240px;
  min-height: 100vh;
  padding: 16px 12px;
  background: var(--bg-primary);
  border-right: 1px solid var(--border);
  transition: width 0.25s var(--ease);
  overflow: hidden;
}

.app-sidebar.collapsed {
  width: 64px;
  padding: 16px 8px;
}

.brand-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 8px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: #fff;
  flex-shrink: 0;
}

.brand-text {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}

.nav-group-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  padding: 16px 16px 8px;
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border: none;
  background: transparent;
}

:deep(.el-menu) {
  border-right: none;
  background: transparent;
}

:deep(.el-menu-item) {
  height: 44px;
  margin-bottom: 2px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.9rem;
}

:deep(.el-menu-item:hover) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

:deep(.el-menu-item.is-active) {
  background: var(--bg-hover);
  color: var(--text-primary);
  font-weight: 600;
}

.sidebar-bottom {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px 4px;
  border-top: 1px solid var(--border);
}

.collapse-toggle {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.collapse-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.agent-status {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.status-dot.healthy {
  background: var(--success);
}

.status-dot.degraded {
  background: var(--danger);
}

.status-text {
  font-size: 0.78rem;
  color: var(--text-secondary);
}
</style>
