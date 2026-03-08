<template>
  <div>
    <div class="page-header">
      <h2>审计日志</h2>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="hover" style="margin-bottom: 16px">
      <el-form :inline="true" :model="filters">
        <el-form-item label="Trace ID">
          <el-input
            v-model="filters.trace_id"
            placeholder="输入 Trace ID"
            clearable
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-select v-model="filters.days" style="width: 130px">
            <el-option label="最近1天" :value="1" />
            <el-option label="最近3天" :value="3" />
            <el-option label="最近7天" :value="7" />
            <el-option label="最近30天" :value="30" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchLogs">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计概览 -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-mini">
          <div class="stat-mini-label">总分析次数</div>
          <div class="stat-mini-value">{{ auditStats.total_analyses || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-mini">
          <div class="stat-mini-label">总 Token 消耗</div>
          <div class="stat-mini-value">{{ (auditStats.total_input_tokens || 0) + (auditStats.total_output_tokens || 0) }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-mini">
          <div class="stat-mini-label">日志条数</div>
          <div class="stat-mini-value">{{ totalLogCount }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 日志列表 (按 trace_id 分组) -->
    <el-card shadow="hover">
      <el-collapse v-model="expandedTraces" v-loading="loading">
        <el-collapse-item
          v-for="group in groupedLogs"
          :key="group.trace_id"
          :name="group.trace_id"
        >
          <template #title>
            <div class="trace-header">
              <el-tag size="small" type="info">{{ group.trace_id }}</el-tag>
              <span class="trace-count">{{ group.events.length }} 个事件</span>
              <span class="trace-time">{{ group.earliest }}</span>
            </div>
          </template>

          <el-table :data="group.events" size="small" border style="width: 100%">
            <el-table-column prop="event_type" label="事件类型" width="160">
              <template #default="{ row }">
                <el-tag
                  :type="eventTypeColor(row.event_type)"
                  size="small"
                >
                  {{ row.event_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="data" label="数据" min-width="300">
              <template #default="{ row }">
                <el-popover placement="top-start" :width="500" trigger="hover">
                  <template #reference>
                    <span style="cursor: pointer; color: #409eff; font-size: 13px">
                      {{ truncateData(row.data) }}
                    </span>
                  </template>
                  <pre style="white-space: pre-wrap; font-size: 12px; max-height: 400px; overflow: auto">{{ formatData(row.data) }}</pre>
                </el-popover>
              </template>
            </el-table-column>
            <el-table-column prop="token_usage" label="Token" width="100">
              <template #default="{ row }">
                {{ row.token_usage || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="180" />
          </el-table>
        </el-collapse-item>
      </el-collapse>

      <el-empty v-if="!loading && groupedLogs.length === 0" description="暂无审计日志" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getAuditLogs, getAuditStats } from '../api'
import { filterAuditLogsByDays } from '../api/view-models.js'

const route = useRoute()

const filters = ref({
  trace_id: typeof route.query.trace_id === 'string' ? route.query.trace_id : '',
  days: Number(route.query.days || 7),
})

const logs = ref([])
const auditStats = ref({})
const loading = ref(false)
const expandedTraces = ref([])

const groupedLogs = computed(() => {
  const map = {}
  for (const log of logs.value) {
    const tid = log.trace_id || 'unknown'
    if (!map[tid]) {
      map[tid] = { trace_id: tid, events: [], earliest: log.created_at }
    }
    map[tid].events.push(log)
    if (log.created_at < map[tid].earliest) {
      map[tid].earliest = log.created_at
    }
  }
  return Object.values(map).sort((a, b) => (b.earliest > a.earliest ? 1 : -1))
})

const totalLogCount = computed(() => logs.value.length)

function eventTypeColor(type) {
  const map = {
    llm_start: '',
    llm_end: 'success',
    tool_call: 'warning',
    tool_result: 'info',
    error: 'danger',
  }
  return map[type] || 'info'
}

function truncateData(data) {
  const str = typeof data === 'string' ? data : JSON.stringify(data)
  return str.length > 80 ? str.slice(0, 80) + '...' : str
}

function formatData(data) {
  try {
    const obj = typeof data === 'string' ? JSON.parse(data) : data
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(data)
  }
}

async function fetchLogs() {
  loading.value = true
  try {
    const params = {}
    if (filters.value.trace_id) params.trace_id = filters.value.trace_id
    const res = await getAuditLogs(params)
    logs.value = filterAuditLogsByDays(res.logs || [], filters.value.days)
  } catch (err) {
    console.error('Failed to fetch audit logs:', err)
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    auditStats.value = await getAuditStats({ days: filters.value.days })
  } catch (err) {
    console.error('Failed to fetch audit stats:', err)
  }
}

function handleReset() {
  filters.value = { trace_id: '', days: 7 }
  fetchLogs()
  fetchStats()
}

onMounted(() => {
  fetchLogs()
  fetchStats()
})

watch(() => route.query, (query) => {
  filters.value.trace_id = typeof query.trace_id === 'string' ? query.trace_id : ''
  filters.value.days = Number(query.days || filters.value.days || 7)
  fetchLogs()
  fetchStats()
})
</script>

<style scoped>
.stat-mini {
  text-align: center;
  padding: 8px;
}

.stat-mini-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 4px;
}

.stat-mini-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.trace-header {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.trace-count {
  font-size: 13px;
  color: #909399;
}

.trace-time {
  font-size: 13px;
  color: #c0c4cc;
  margin-left: auto;
  padding-right: 16px;
}
</style>
