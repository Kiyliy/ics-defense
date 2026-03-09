<template>
  <div class="system-config">
    <el-form :model="form" label-position="top" class="config-form" v-loading="loading">

      <!-- 数据源配置 -->
      <h3 class="section-title">数据源配置</h3>

      <el-form-item label="允许的事件来源">
        <div class="source-editor">
          <div class="source-tags">
            <el-tag
              v-for="src in form.validSources"
              :key="src"
              closable
              type="info"
              class="source-tag"
              @close="removeSource(src)"
            >
              {{ src }}
            </el-tag>
          </div>
          <div class="source-add">
            <el-input
              v-model="newSource"
              placeholder="输入新数据源名称"
              size="small"
              style="width: 180px"
              @keyup.enter="addSource"
            />
            <el-button size="small" @click="addSource" :disabled="!newSource.trim()">添加</el-button>
          </div>
        </div>
        <p class="field-description">
          通过 /api/alerts/ingest 接入的事件必须声明 source，只有在此列表中的来源才被允许。
        </p>
      </el-form-item>

      <el-form-item label="告警聚类时间窗口">
        <div class="inline-field">
          <el-input-number
            v-model="form.clusteringWindowHours"
            :min="1"
            :max="72"
            :step="1"
            controls-position="right"
            style="width: 160px"
          />
          <span class="unit-label">小时</span>
        </div>
        <p class="field-description">
          相同来源、标题、严重度的告警在此窗口内合并计数，避免重复告警。
        </p>
      </el-form-item>

      <!-- 告警策略 -->
      <h3 class="section-title">告警策略</h3>

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

      <!-- 服务与通知 -->
      <h3 class="section-title">服务与通知</h3>

      <el-form-item label="Agent 服务地址">
        <el-input
          v-model="form.agentServiceUrl"
          placeholder="http://localhost:8002"
          clearable
        />
        <p class="field-description">Python Agent Service 的内部地址，用于调用 MCP 分析。</p>
      </el-form-item>

      <el-form-item label="通知渠道">
        <el-select v-model="form.notificationProvider" style="width: 100%">
          <el-option label="飞书 Bot" value="feishu" />
          <el-option label="飞书应用" value="feishu-app" />
          <el-option label="无（关闭通知）" value="noop" />
        </el-select>
      </el-form-item>

      <el-form-item label="通知重试">
        <div class="retry-row">
          <div class="retry-item">
            <span class="retry-label">最大重试</span>
            <el-input-number v-model="form.notificationMaxRetries" :min="0" :max="20" :step="1" controls-position="right" size="small" style="width: 110px" />
            <span class="unit-label">次</span>
          </div>
          <div class="retry-item">
            <span class="retry-label">基础延迟</span>
            <el-input-number v-model="form.notificationBaseDelay" :min="100" :max="60000" :step="500" controls-position="right" size="small" style="width: 110px" />
            <span class="unit-label">ms</span>
          </div>
          <div class="retry-item">
            <span class="retry-label">最大延迟</span>
            <el-input-number v-model="form.notificationMaxDelay" :min="1000" :max="120000" :step="1000" controls-position="right" size="small" style="width: 110px" />
            <span class="unit-label">ms</span>
          </div>
        </div>
      </el-form-item>

      <!-- 性能与限制 -->
      <h3 class="section-title">性能与限制</h3>

      <el-form-item label="单次事件接入上限">
        <el-input-number
          v-model="form.maxBatchSize"
          :min="100"
          :max="10000"
          :step="100"
          controls-position="right"
          style="width: 200px"
        />
      </el-form-item>

      <el-form-item label="Chat 单次最大消息数">
        <el-input-number
          v-model="form.chatMaxMessages"
          :min="10"
          :max="200"
          :step="10"
          controls-position="right"
          style="width: 200px"
        />
      </el-form-item>

      <el-form-item label="请求体大小上限">
        <el-input v-model="form.bodyLimit" placeholder="1mb" style="width: 200px" />
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
import { getSettings, updateSettings } from '../../api'

const loading = ref(false)
const saving = ref(false)
const newSource = ref('')

const form = reactive({
  // 数据源
  validSources: [],
  clusteringWindowHours: 1,
  maxBatchSize: 1000,
  // 告警策略
  escalationThreshold: 'high',
  autoApprovalEnabled: false,
  // 服务
  agentServiceUrl: '',
  // 通知
  notificationProvider: 'feishu',
  notificationMaxRetries: 5,
  notificationBaseDelay: 1000,
  notificationMaxDelay: 30000,
  // 性能
  chatMaxMessages: 50,
  bodyLimit: '1mb',
})

const addSource = () => {
  const s = newSource.value.trim().toLowerCase()
  if (s && !form.validSources.includes(s)) {
    form.validSources.push(s)
  }
  newSource.value = ''
}

const removeSource = (src) => {
  form.validSources = form.validSources.filter(s => s !== src)
}

onMounted(async () => {
  loading.value = true
  try {
    const res = await getSettings()
    const configs = res.configs || []
    const map = Object.fromEntries(configs.map(c => [c.key, c.value]))

    // 数据源
    const sources = map['ingest.valid_sources'] || 'waf,nids,hids,pikachu,soc'
    form.validSources = sources.split(',').map(s => s.trim()).filter(Boolean)
    form.clusteringWindowHours = parseInt(map['ingest.clustering_window_hours']) || 1
    form.maxBatchSize = parseInt(map['ingest.max_batch_size']) || 1000

    // 告警策略
    form.escalationThreshold = map['system.escalation_threshold'] || 'high'
    form.autoApprovalEnabled = map['system.auto_approval'] === 'true'

    // 服务
    form.agentServiceUrl = map['agent.service_url'] || ''

    // 通知
    form.notificationProvider = map['notification.provider'] || 'feishu'
    form.notificationMaxRetries = parseInt(map['notification.max_retries']) || 5
    form.notificationBaseDelay = parseInt(map['notification.base_delay_ms']) || 1000
    form.notificationMaxDelay = parseInt(map['notification.max_delay_ms']) || 30000

    // 性能
    form.chatMaxMessages = parseInt(map['chat.max_messages']) || 50
    form.bodyLimit = map['request.body_limit'] || '1mb'
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
      'ingest.valid_sources': form.validSources.join(','),
      'ingest.clustering_window_hours': String(form.clusteringWindowHours),
      'ingest.max_batch_size': String(form.maxBatchSize),
      'system.escalation_threshold': form.escalationThreshold,
      'system.auto_approval': String(form.autoApprovalEnabled),
      'agent.service_url': form.agentServiceUrl,
      'notification.provider': form.notificationProvider,
      'notification.max_retries': String(form.notificationMaxRetries),
      'notification.base_delay_ms': String(form.notificationBaseDelay),
      'notification.max_delay_ms': String(form.notificationMaxDelay),
      'chat.max_messages': String(form.chatMaxMessages),
      'request.body_limit': form.bodyLimit,
    })
    ElMessage.success('系统配置已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.system-config {
  max-width: 620px;
}

.section-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 32px 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.section-title:first-child {
  margin-top: 0;
}

.config-form :deep(.el-form-item) {
  margin-bottom: 24px;
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

.source-editor {
  width: 100%;
}

.source-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  min-height: 44px;
  align-items: center;
}

.source-tag {
  font-weight: 600;
  font-size: 0.82rem;
}

.source-add {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.inline-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unit-label {
  font-size: 0.86rem;
  color: var(--text-secondary);
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

.retry-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.retry-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.retry-label {
  font-size: 0.84rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.form-actions {
  padding-top: 8px;
}
</style>
