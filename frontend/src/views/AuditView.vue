<template>
  <div>
    <div class="page-header">
      <div class="page-header-copy">
        <h2>审计日志</h2>
        <p class="page-subtitle">
          审计模型调用、工具执行与 trace 级链路信息，为复盘、问责与规则优化提供高可信依据。
        </p>
      </div>
      <div class="page-header-meta">
        <span>Traceability</span>
        <span>{{ totalLogCount }} Events</span>
      </div>
    </div>

    <el-card shadow="hover" class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="Trace ID">
          <el-input v-model="filters.trace_id" placeholder="按 trace_id 筛选" clearable style="width: 220px" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-select v-model="filters.days" style="width: 140px">
            <el-option :value="1" label="最近 1 天" />
            <el-option :value="7" label="最近 7 天" />
            <el-option :value="30" label="最近 30 天" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchLogs(); fetchStats()">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="18" style="margin-bottom: 18px">
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="stat-mini">
          <div class="stat-mini-label">总分析次数</div>
          <div class="stat-mini-value">{{ auditStats.total_analyses || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="stat-mini">
          <div class="stat-mini-label">总 Token 消耗</div>
          <div class="stat-mini-value">{{ (auditStats.total_input_tokens || 0) + (auditStats.total_output_tokens || 0) }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="stat-mini">
          <div class="stat-mini-label">日志条数</div>
          <div class="stat-mini-value">{{ totalLogCount }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover">
      <template #header>
        <div class="section-title">
          <span>Trace 分组日志</span>
          <small>Grouped Event Timeline</small>
        </div>
      </template>

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

          <el-table :data="group.events" size="small" border class="data-table">
            <el-table-column prop="event_type" label="事件类型" width="160">
              <template #default="{ row }">
                <el-tag :type="eventTypeColor(row.event_type)" size="small">
                  {{ row.event_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="data" label="数据" min-width="300">
              <template #default="{ row }">
                <el-popover placement="top-start" :width="500" trigger="hover">
                  <template #reference>
                    <span class="link-text">{{ truncateData(row.data) }}</span>
                  </template>
                  <pre class="detail-pre">{{ formatData(row.data) }}</pre>
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
  padding: 10px;
}

.stat-mini-label {
  font-size: 0.84rem;
  color: #64748b;
  margin-bottom: 6px;
}

.stat-mini-value {
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #0f172a;
}

.link-text {
  cursor: pointer;
  color: #2563eb;
  font-size: 0.84rem;
  font-weight: 600;
}
</style>
