<template>
  <div class="notify-rules">
    <table class="rules-table">
      <thead>
        <tr>
          <th>事件</th>
          <th>渠道</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="rule in rules" :key="rule.id">
          <td class="rule-event">{{ rule.event }}</td>
          <td class="rule-channel">
            <span class="channel-pill">{{ rule.channel }}</span>
          </td>
          <td>
            <el-switch
              v-model="rule.enabled"
              @change="handleToggle(rule)"
              active-color="var(--success)"
            />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getNotificationRules, saveNotificationRule } from '../../api'

const rules = ref([])

async function fetchRules() {
  try {
    const res = await getNotificationRules()
    rules.value = res.rules || []
  } catch (err) {
    console.error('Failed to fetch notification rules:', err)
    // Fallback to empty list on error
    rules.value = []
  }
}

async function handleToggle(rule) {
  const status = rule.enabled ? '已启用' : '已禁用'
  try {
    await saveNotificationRule({ id: rule.id, enabled: rule.enabled })
    ElMessage.success(`${rule.event} 通知${status}`)
  } catch (err) {
    // Revert toggle on failure
    rule.enabled = !rule.enabled
    ElMessage.error('更新规则失败')
  }
}

onMounted(() => {
  fetchRules()
})
</script>

<style scoped>
.rules-table {
  width: 100%;
  border-collapse: collapse;
}

.rules-table th {
  text-align: left;
  padding: 10px 16px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
}

.rules-table td {
  padding: 14px 16px;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.rules-table tbody tr:hover {
  background: var(--bg-hover);
}

.rule-event {
  font-weight: 600;
}

.channel-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: var(--accent-bg);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 600;
}
</style>
