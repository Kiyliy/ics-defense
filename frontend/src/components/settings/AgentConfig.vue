<template>
  <div class="agent-config">
    <el-form :model="form" label-position="top" class="config-form">
      <el-form-item label="Model 选择">
        <el-select v-model="form.model" placeholder="选择模型" style="width: 100%">
          <el-option label="gpt-4o" value="gpt-4o" />
          <el-option label="gpt-4o-mini" value="gpt-4o-mini" />
          <el-option label="claude-3-5-sonnet" value="claude-3-5-sonnet" />
          <el-option label="claude-3-opus" value="claude-3-opus" />
          <el-option label="deepseek-v3" value="deepseek-v3" />
          <el-option label="deepseek-r1" value="deepseek-r1" />
        </el-select>
      </el-form-item>

      <el-form-item label="Temperature">
        <el-slider
          v-model="form.temperature"
          :min="0"
          :max="1"
          :step="0.1"
          show-input
          :show-input-controls="false"
        />
      </el-form-item>

      <el-form-item label="Max Tokens">
        <el-input-number
          v-model="form.maxTokens"
          :min="100"
          :max="8000"
          :step="100"
          controls-position="right"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="MCP 服务器">
        <div class="mcp-servers">
          <el-tag
            v-for="server in mcpServers"
            :key="server"
            type="info"
            class="mcp-tag"
            disable-transitions
          >
            {{ server }}
          </el-tag>
          <span v-if="mcpServers.length === 0" class="empty-hint">暂无连接的 MCP 服务器</span>
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
  model: 'gpt-4o',
  temperature: 0.7,
  maxTokens: 4000,
})

const mcpServers = ref([
  'suricata-mcp',
  'network-monitor',
  'threat-intel',
])

const handleSave = () => {
  ElMessage.success('Agent 配置已保存')
}
</script>

<style scoped>
.agent-config {
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

.mcp-servers {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  min-height: 44px;
  width: 100%;
  align-items: center;
}

.mcp-tag {
  font-weight: 600;
  font-size: 0.82rem;
}

.empty-hint {
  font-size: 0.84rem;
  color: var(--text-muted);
}

.form-actions {
  padding-top: 8px;
}
</style>
