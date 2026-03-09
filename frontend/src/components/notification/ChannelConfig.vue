<template>
  <div class="channel-config">
    <div class="section-toolbar">
      <el-button type="primary" size="small" @click="toggleForm">
        {{ showForm ? '取消' : '+ 添加渠道' }}
      </el-button>
    </div>

    <!-- Add Channel Form -->
    <div v-if="showForm" class="channel-form">
      <div class="form-row">
        <el-select v-model="form.type" placeholder="渠道类型" style="width: 160px">
          <el-option label="飞书" value="feishu" />
          <el-option label="钉钉" value="dingtalk" />
          <el-option label="Webhook" value="webhook" />
        </el-select>
        <el-input
          v-model="form.webhook"
          placeholder="Webhook URL"
          style="flex: 1"
        />
        <el-button type="primary" @click="addChannel" :disabled="!form.type || !form.webhook">
          保存
        </el-button>
      </div>
    </div>

    <!-- Channel List -->
    <div v-if="channels.length > 0" class="channel-list">
      <div v-for="ch in channels" :key="ch.id" class="channel-card">
        <div class="channel-info">
          <span class="channel-type-badge">{{ typeLabel(ch.type) }}</span>
          <span class="channel-url">{{ maskUrl(ch.webhook) }}</span>
        </div>
        <div class="channel-actions">
          <el-button size="small" @click="testChannel(ch)" :loading="ch._testing">
            测试
          </el-button>
          <el-button size="small" @click="editChannel(ch)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="removeChannel(ch)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <p class="empty-title">暂未配置通知渠道</p>
      <p class="empty-desc">点击上方按钮添加飞书、钉钉或 Webhook 渠道</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getNotificationChannels,
  saveNotificationChannel,
  testNotificationChannel,
  deleteNotificationChannel,
} from '../../api'

const showForm = ref(false)
const editingId = ref(null)
const form = reactive({ type: 'feishu', webhook: '' })
const channels = ref([])

function toggleForm() {
  showForm.value = !showForm.value
  if (!showForm.value) {
    editingId.value = null
    form.webhook = ''
  }
}

const typeLabels = { feishu: '飞书', dingtalk: '钉钉', webhook: 'Webhook' }
function typeLabel(type) {
  return typeLabels[type] || type
}

function maskUrl(url) {
  if (!url || url.length < 20) return url
  return url.slice(0, 30) + '******' + url.slice(-6)
}

async function fetchChannels() {
  try {
    const res = await getNotificationChannels()
    channels.value = (res.channels || []).map((ch) => ({ ...ch, _testing: false }))
  } catch (err) {
    console.error('Failed to fetch channels:', err)
  }
}

async function addChannel() {
  try {
    await saveNotificationChannel({
      id: editingId.value,
      type: form.type,
      webhook: form.webhook,
    })
    if (editingId.value !== null) {
      ElMessage.success('渠道已更新')
      editingId.value = null
    } else {
      ElMessage.success('渠道已添加')
    }
    form.webhook = ''
    showForm.value = false
    await fetchChannels()
  } catch (err) {
    ElMessage.error('保存渠道失败')
  }
}

async function removeChannel(ch) {
  try {
    await deleteNotificationChannel(ch.id)
    ElMessage.success('渠道已删除')
    await fetchChannels()
  } catch (err) {
    ElMessage.error('删除渠道失败')
  }
}

function editChannel(ch) {
  editingId.value = ch.id
  form.type = ch.type
  form.webhook = ch.webhook
  showForm.value = true
}

async function testChannel(ch) {
  ch._testing = true
  try {
    await testNotificationChannel(ch.id)
    ElMessage.success(`已向 ${typeLabel(ch.type)} 发送测试通知`)
  } catch (err) {
    ElMessage.error('测试通知发送失败')
  } finally {
    ch._testing = false
  }
}

onMounted(() => {
  fetchChannels()
})
</script>

<style scoped>
.section-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.channel-form {
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-page);
}

.form-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.channel-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.channel-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-primary);
}

.channel-info {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.channel-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  background: var(--accent-bg);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 700;
  white-space: nowrap;
}

.channel-url {
  font-size: 0.85rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px;
  text-align: center;
}

.empty-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.empty-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
}
</style>
