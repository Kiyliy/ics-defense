<template>
  <div class="agent-config">
    <el-form :model="form" label-position="top" class="config-form" v-loading="loading">
      <el-form-item label="API Base URL">
        <el-input
          v-model="form.baseUrl"
          placeholder="https://api.x.ai/v1"
          clearable
        />
        <p class="field-description">OpenAI 兼容接口地址，如 xAI、OpenAI、本地部署等。</p>
      </el-form-item>

      <el-form-item label="API Key">
        <el-input
          v-model="form.apiKey"
          placeholder="输入 API Key"
          type="password"
          show-password
          clearable
        />
      </el-form-item>

      <el-form-item label="Model">
        <el-select
          v-model="form.model"
          placeholder="选择或输入模型名称"
          style="width: 100%"
          filterable
          allow-create
          default-first-option
        >
          <el-option-group label="Grok (xAI)">
            <el-option label="grok-4-1-fast-non-reasoning" value="grok-4-1-fast-non-reasoning" />
            <el-option label="grok-3-mini-fast" value="grok-3-mini-fast" />
            <el-option label="grok-3-fast" value="grok-3-fast" />
            <el-option label="grok-3" value="grok-3" />
            <el-option label="grok-3-mini" value="grok-3-mini" />
          </el-option-group>
          <el-option-group label="其他">
            <el-option label="gpt-4o" value="gpt-4o" />
            <el-option label="deepseek-v3" value="deepseek-v3" />
            <el-option label="deepseek-r1" value="deepseek-r1" />
          </el-option-group>
        </el-select>
        <p class="field-description">支持下拉选择或手动输入任意模型名称。</p>
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
          :max="32000"
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
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings, getAgentStatus } from '../../api'

const loading = ref(false)
const saving = ref(false)

const form = reactive({
  model: '',
  baseUrl: '',
  apiKey: '',
  temperature: 0.5,
  maxTokens: 4000,
})

const mcpServers = ref([])

onMounted(async () => {
  loading.value = true
  try {
    const [settingsRes, agentRes] = await Promise.all([
      getSettings(),
      getAgentStatus().catch(() => null),
    ])
    const configs = settingsRes.configs || []
    const map = Object.fromEntries(configs.map(c => [c.key, c.value]))
    form.model = map['llm.model'] || ''
    form.baseUrl = map['llm.base_url'] || ''
    form.apiKey = map['llm.api_key'] || ''
    form.temperature = parseFloat(map['llm.temperature']) || 0.5
    form.maxTokens = parseInt(map['llm.max_tokens']) || 4000
    if (agentRes?.mcp_servers) {
      mcpServers.value = agentRes.mcp_servers
    }
  } catch (e) {
    console.error('Failed to load settings:', e)
  } finally {
    loading.value = false
  }
})

const handleSave = async () => {
  saving.value = true
  try {
    await updateSettings({
      'llm.model': form.model,
      'llm.base_url': form.baseUrl,
      'llm.api_key': form.apiKey,
      'llm.temperature': String(form.temperature),
      'llm.max_tokens': String(form.maxTokens),
    })
    ElMessage.success('Agent 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
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

.field-description {
  margin-top: 6px;
  font-size: 0.82rem;
  color: var(--text-muted);
  line-height: 1.5;
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
