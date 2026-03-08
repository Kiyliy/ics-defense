<template>
  <div class="settings-view">
    <div class="page-header">
      <div class="page-header-copy">
        <h1>设置</h1>
        <p class="page-subtitle">管理 Agent 运行参数与系统级配置</p>
      </div>
    </div>

    <div class="settings-body">
      <el-tabs v-model="activeTab" tab-position="left" class="settings-tabs">
        <el-tab-pane label="Agent 配置" name="agent">
          <AgentConfig />
        </el-tab-pane>
        <el-tab-pane label="系统配置" name="system">
          <SystemConfig />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AgentConfig from '../components/settings/AgentConfig.vue'
import SystemConfig from '../components/settings/SystemConfig.vue'

const activeTab = ref('agent')
</script>

<style scoped>
.settings-view {
  padding: 0 0 40px;
}

.page-header {
  margin-bottom: 28px;
}

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.page-subtitle {
  margin-top: 4px;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.settings-body {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.settings-tabs :deep(.el-tabs__header) {
  border-right: 1px solid var(--border);
  margin-right: 0;
}

.settings-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.settings-tabs :deep(.el-tabs__item) {
  height: 44px;
  line-height: 44px;
  font-weight: 600;
  font-size: 0.88rem;
  color: var(--text-secondary);
  padding: 0 28px;
  text-align: left;
  justify-content: flex-start;
}

.settings-tabs :deep(.el-tabs__item.is-active) {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.settings-tabs :deep(.el-tabs__item:hover) {
  color: var(--text-primary);
}

.settings-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--text-primary);
}

.settings-tabs :deep(.el-tabs__content) {
  padding: 28px 32px;
}
</style>
