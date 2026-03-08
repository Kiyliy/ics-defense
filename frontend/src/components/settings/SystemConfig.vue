<template>
  <div class="system-config">
    <el-form :model="form" label-position="top" class="config-form">
      <el-form-item label="告警自动升级阈值">
        <el-select v-model="form.escalationThreshold" placeholder="选择严重级别" style="width: 100%">
          <el-option label="Low" value="low" />
          <el-option label="Medium" value="medium" />
          <el-option label="High" value="high" />
          <el-option label="Critical" value="critical" />
        </el-select>
      </el-form-item>

      <el-form-item label="自动审批规则">
        <div class="auto-approval-row">
          <el-switch v-model="form.autoApprovalEnabled" />
          <span class="approval-label">
            {{ form.autoApprovalEnabled ? '已启用' : '已禁用' }}
          </span>
        </div>
        <p class="field-description">
          当告警严重级别低于阈值时，自动批准 Agent 建议的响应操作，无需人工审核。
        </p>
      </el-form-item>

      <el-form-item label="数据源配置">
        <div class="data-sources">
          <div
            v-for="source in dataSources"
            :key="source.name"
            class="source-item"
          >
            <span class="source-name">{{ source.name }}</span>
            <el-tag
              :type="source.connected ? 'success' : 'danger'"
              size="small"
              disable-transitions
            >
              {{ source.connected ? '已连接' : '未连接' }}
            </el-tag>
          </div>
          <span v-if="dataSources.length === 0" class="empty-hint">暂无配置的数据源</span>
        </div>
      </el-form-item>

      <div class="form-actions">
        <el-button type="primary" @click="handleSave">保存</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

const form = reactive({
  escalationThreshold: 'high',
  autoApprovalEnabled: false,
})

const dataSources = ref([
  { name: 'Suricata IDS', connected: true },
  { name: 'OPC UA Monitor', connected: true },
  { name: 'Modbus TCP Logger', connected: false },
  { name: 'Syslog Collector', connected: true },
])

const handleSave = () => {
  ElMessage.success('系统配置已保存')
}
</script>

<style scoped>
.system-config {
  max-width: 560px;
}

.config-form :deep(.el-form-item) {
  margin-bottom: 28px;
}

.config-form :deep(.el-form-item__label) {
  font-weight: 600;
  font-size: 0.88rem;
  color: var(--text-primary);
  padding-bottom: 8px;
}

.auto-approval-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.approval-label {
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.field-description {
  margin-top: 8px;
  font-size: 0.82rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.data-sources {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  overflow: hidden;
  width: 100%;
}

.source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}

.source-item:last-child {
  border-bottom: none;
}

.source-name {
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--text-primary);
}

.empty-hint {
  padding: 12px 14px;
  font-size: 0.84rem;
  color: var(--text-muted);
}

.form-actions {
  padding-top: 8px;
}
</style>
