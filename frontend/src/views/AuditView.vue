<template>
  <div class="audit-page">
    <!-- Header -->
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

    <!-- Stats Row -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="icon-wrapper" style="background: linear-gradient(135deg, #6366f1, #4f46e5)">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/>
          </svg>
        </div>
        <div class="info">
          <div class="label">总分析次数</div>
          <div class="value">{{ auditStats.total_analyses || 0 }}</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="icon-wrapper" style="background: linear-gradient(135deg, #f59e0b, #d97706)">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
          </svg>
        </div>
        <div class="info">
          <div class="label">Token 消耗</div>
          <div class="value">{{ formatNumber(totalTokens) }}</div>
          <div class="stat-detail" v-if="auditStats.total_input_tokens">
            <span class="detail-chip input">IN {{ formatNumber(auditStats.total_input_tokens) }}</span>
            <span class="detail-chip output">OUT {{ formatNumber(auditStats.total_output_tokens || 0) }}</span>
          </div>
        </div>
      </div>

      <div class="stat-card">
        <div class="icon-wrapper" style="background: linear-gradient(135deg, #22c55e, #16a34a)">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
        </div>
        <div class="info">
          <div class="label">日志条数</div>
          <div class="value">{{ totalLogCount }}</div>
          <div class="stat-detail" v-if="groupedLogs.length">
            <span class="detail-chip trace">{{ groupedLogs.length }} Traces</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="filter-inputs">
        <div class="filter-group">
          <label>Trace ID</label>
          <el-input
            v-model="filters.trace_id"
            placeholder="输入 trace_id 精确筛选..."
            clearable
            prefix-icon="Search"
            class="filter-input"
          />
        </div>
        <div class="filter-group">
          <label>时间范围</label>
          <el-select v-model="filters.days" class="filter-select">
            <el-option :value="1" label="最近 1 天" />
            <el-option :value="7" label="最近 7 天" />
            <el-option :value="30" label="最近 30 天" />
          </el-select>
        </div>
      </div>
      <div class="filter-actions">
        <el-button type="primary" @click="fetchLogs(); fetchStats()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          查询
        </el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>
    </div>

    <!-- Timeline Section -->
    <div class="timeline-section" v-loading="loading">
      <div class="section-header">
        <div class="section-title-group">
          <h3>Trace 链路时间线</h3>
          <span class="section-badge">{{ groupedLogs.length }} traces</span>
        </div>
        <p class="section-desc">每条 Trace 记录一次完整的 AI 分析链路，展开查看详细事件流</p>
      </div>

      <TransitionGroup name="trace-list" tag="div" class="trace-list">
        <div
          v-for="group in groupedLogs"
          :key="group.trace_id"
          class="trace-card"
          :class="{ expanded: expandedTraces.includes(group.trace_id) }"
        >
          <!-- Trace Card Header -->
          <div class="trace-card-header" @click="toggleTrace(group.trace_id)">
            <div class="trace-indicator">
              <div class="trace-dot" :class="traceStatusClass(group)"></div>
              <div class="trace-line"></div>
            </div>
            <div class="trace-info">
              <div class="trace-title-row">
                <span class="trace-id-badge">{{ shortTraceId(group.trace_id) }}</span>
                <div class="trace-meta-chips">
                  <span class="meta-chip events">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></svg>
                    {{ group.events.length }} 事件
                  </span>
                  <span class="meta-chip tokens" v-if="group.totalTokens">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                    {{ formatNumber(group.totalTokens) }} tokens
                  </span>
                </div>
              </div>
              <div class="trace-event-preview">
                <span
                  v-for="type in group.eventTypes"
                  :key="type"
                  class="event-type-dot"
                  :class="'dot-' + eventTypeCategory(type)"
                  :title="type"
                ></span>
              </div>
              <div class="trace-time-row">
                <span class="trace-time">{{ formatTime(group.earliest) }}</span>
                <span class="trace-duration" v-if="group.duration">{{ group.duration }}</span>
              </div>
            </div>
            <div class="trace-expand-icon" :class="{ rotated: expandedTraces.includes(group.trace_id) }">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </div>
          </div>

          <!-- Trace Events Timeline -->
          <Transition name="slide-down">
            <div v-if="expandedTraces.includes(group.trace_id)" class="trace-events">
              <div
                v-for="(evt, idx) in group.events"
                :key="idx"
                class="event-node"
                :class="'event-' + eventTypeCategory(evt.event_type)"
              >
                <div class="event-rail">
                  <div class="event-dot-outer">
                    <div class="event-dot-inner"></div>
                  </div>
                  <div v-if="idx < group.events.length - 1" class="event-connector"></div>
                </div>
                <div class="event-content">
                  <div class="event-header">
                    <span class="event-type-badge" :class="'badge-' + eventTypeCategory(evt.event_type)">
                      {{ eventTypeLabel(evt.event_type) }}
                    </span>
                    <span class="event-time">{{ formatEventTime(evt.created_at) }}</span>
                  </div>
                  <div class="event-body">
                    <div class="event-data-preview" @click.stop="toggleEventDetail(group.trace_id, idx)">
                      <span class="data-text">{{ truncateData(evt.data) }}</span>
                      <span class="expand-hint" v-if="dataLength(evt.data) > 80">
                        {{ isEventExpanded(group.trace_id, idx) ? '收起' : '展开' }}
                      </span>
                    </div>
                    <Transition name="fade">
                      <pre v-if="isEventExpanded(group.trace_id, idx)" class="event-data-full">{{ formatData(evt.data) }}</pre>
                    </Transition>
                  </div>
                  <div class="event-footer" v-if="evt.token_usage">
                    <div class="token-bar">
                      <div class="token-info">
                        <span class="token-label">Token</span>
                        <span class="token-value">{{ formatTokenUsage(evt.token_usage) }}</span>
                      </div>
                      <div class="token-progress" v-if="parseTokens(evt.token_usage)">
                        <div
                          class="token-progress-input"
                          :style="{ width: tokenInputPct(evt.token_usage, group.maxTokens) + '%' }"
                        ></div>
                        <div
                          class="token-progress-output"
                          :style="{ width: tokenOutputPct(evt.token_usage, group.maxTokens) + '%' }"
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </TransitionGroup>

      <div v-if="!loading && groupedLogs.length === 0" class="empty-state">
        <div class="empty-icon">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <h4>暂无审计日志</h4>
        <p>当 AI 分析任务运行后，链路追踪日志将在此展示</p>
      </div>
    </div>
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
const expandedEvents = ref(new Set())

const totalTokens = computed(() =>
  (auditStats.value.total_input_tokens || 0) + (auditStats.value.total_output_tokens || 0)
)

const groupedLogs = computed(() => {
  const map = {}
  for (const log of logs.value) {
    const tid = log.trace_id || 'unknown'
    if (!map[tid]) {
      map[tid] = { trace_id: tid, events: [], earliest: log.created_at, latest: log.created_at, totalTokens: 0, maxTokens: 0, eventTypes: new Set() }
    }
    map[tid].events.push(log)
    map[tid].eventTypes.add(log.event_type)
    if (log.created_at < map[tid].earliest) map[tid].earliest = log.created_at
    if (log.created_at > map[tid].latest) map[tid].latest = log.created_at

    const tokens = parseTokens(log.token_usage)
    if (tokens) {
      const total = (tokens.input || 0) + (tokens.output || 0)
      map[tid].totalTokens += total
      if (total > map[tid].maxTokens) map[tid].maxTokens = total
    }
  }

  return Object.values(map)
    .map(g => {
      g.eventTypes = [...g.eventTypes]
      g.duration = calcDuration(g.earliest, g.latest)
      return g
    })
    .sort((a, b) => (b.earliest > a.earliest ? 1 : -1))
})

const totalLogCount = computed(() => logs.value.length)

function toggleTrace(traceId) {
  const idx = expandedTraces.value.indexOf(traceId)
  if (idx >= 0) expandedTraces.value.splice(idx, 1)
  else expandedTraces.value.push(traceId)
}

function toggleEventDetail(traceId, idx) {
  const key = `${traceId}:${idx}`
  if (expandedEvents.value.has(key)) expandedEvents.value.delete(key)
  else expandedEvents.value.add(key)
}

function isEventExpanded(traceId, idx) {
  return expandedEvents.value.has(`${traceId}:${idx}`)
}

function shortTraceId(id) {
  if (!id || id === 'unknown') return 'unknown'
  return id.slice(0, 8) + '...'
}

function traceStatusClass(group) {
  const types = group.eventTypes
  if (types.includes('error')) return 'dot-error'
  if (types.includes('analysis_finished') || types.includes('decision_made')) return 'dot-success'
  return 'dot-active'
}

function eventTypeCategory(type) {
  if (type.includes('error')) return 'error'
  if (type.includes('llm') || type.includes('plan')) return 'llm'
  if (type.includes('tool')) return 'tool'
  if (type.includes('decision') || type.includes('finished')) return 'decision'
  return 'default'
}

function eventTypeLabel(type) {
  const labels = {
    analysis_started: 'Analysis Start',
    plan_generated: 'Plan Generated',
    llm_call: 'LLM Call',
    llm_summary_call: 'LLM Summary',
    tool_call: 'Tool Call',
    tool_result: 'Tool Result',
    decision_made: 'Decision',
    analysis_finished: 'Finished',
    error: 'Error',
  }
  return labels[type] || type.replace(/_/g, ' ')
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr.replace(' ', 'T'))
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatEventTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr.replace(' ', 'T'))
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function calcDuration(start, end) {
  if (!start || !end) return ''
  const ms = new Date(end.replace(' ', 'T')) - new Date(start.replace(' ', 'T'))
  if (ms < 1000) return ''
  if (ms < 60000) return Math.round(ms / 1000) + 's'
  return Math.round(ms / 60000) + 'min'
}

function formatNumber(n) {
  if (!n) return '0'
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

function eventTypeColor(type) {
  const map = { llm_start: '', llm_end: 'success', tool_call: 'warning', tool_result: 'info', error: 'danger' }
  return map[type] || 'info'
}

function truncateData(data) {
  const str = typeof data === 'string' ? data : JSON.stringify(data)
  return str.length > 80 ? str.slice(0, 80) + '...' : str
}

function dataLength(data) {
  const str = typeof data === 'string' ? data : JSON.stringify(data)
  return str.length
}

function formatData(data) {
  try {
    const obj = typeof data === 'string' ? JSON.parse(data) : data
    return JSON.stringify(obj, null, 2)
  } catch { return String(data) }
}

function parseTokens(usage) {
  if (!usage) return null
  if (typeof usage === 'object') return usage
  try { return JSON.parse(usage) } catch { return null }
}

function formatTokenUsage(usage) {
  const t = parseTokens(usage)
  if (!t) return String(usage)
  const inp = t.input_tokens || t.prompt_tokens || 0
  const out = t.output_tokens || t.completion_tokens || 0
  return `${formatNumber(inp)} in / ${formatNumber(out)} out`
}

function tokenInputPct(usage, max) {
  const t = parseTokens(usage)
  if (!t || !max) return 0
  return Math.min(100, ((t.input_tokens || t.prompt_tokens || 0) / max) * 100)
}

function tokenOutputPct(usage, max) {
  const t = parseTokens(usage)
  if (!t || !max) return 0
  return Math.min(100, ((t.output_tokens || t.completion_tokens || 0) / max) * 100)
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

onMounted(() => { fetchLogs(); fetchStats() })

watch(() => route.query, (query) => {
  filters.value.trace_id = typeof query.trace_id === 'string' ? query.trace_id : ''
  filters.value.days = Number(query.days || filters.value.days || 7)
  fetchLogs()
  fetchStats()
})
</script>

<style scoped>
/* ===== Stats Row ===== */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  margin-bottom: 22px;
}

.stat-detail {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.detail-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.detail-chip.input {
  background: rgba(99, 102, 241, 0.12);
  color: #6366f1;
}

.detail-chip.output {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.detail-chip.trace {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

/* ===== Filter Bar ===== */
.filter-bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  margin-bottom: 22px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--app-radius-md);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--app-shadow-soft);
  backdrop-filter: blur(16px);
}

.filter-inputs {
  display: flex;
  gap: 20px;
  flex: 1;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-group label {
  font-size: 0.78rem;
  font-weight: 700;
  color: #475569;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.filter-input {
  width: 280px;
}

.filter-select {
  width: 160px;
}

.filter-actions {
  display: flex;
  gap: 10px;
}

/* ===== Timeline Section ===== */
.timeline-section {
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--app-radius-lg);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--app-shadow-soft);
  backdrop-filter: blur(16px);
}

.section-header {
  margin-bottom: 28px;
}

.section-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}

.section-title-group h3 {
  font-size: 1.15rem;
  font-weight: 700;
  color: #0f172a;
}

.section-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: 999px;
  background: rgba(79, 140, 255, 0.1);
  color: #2563eb;
  font-size: 0.78rem;
  font-weight: 700;
}

.section-desc {
  font-size: 0.88rem;
  color: #64748b;
  line-height: 1.6;
}

/* ===== Trace Card ===== */
.trace-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.trace-card {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.trace-card:hover {
  border-color: rgba(79, 140, 255, 0.3);
  box-shadow: 0 8px 30px rgba(79, 140, 255, 0.08);
}

.trace-card.expanded {
  border-color: rgba(79, 140, 255, 0.24);
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
}

.trace-card-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 22px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.trace-card-header:hover {
  background: rgba(79, 140, 255, 0.03);
}

/* Trace Indicator */
.trace-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.trace-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 3px solid;
  transition: all 0.3s;
}

.trace-dot.dot-active {
  border-color: #4f8cff;
  background: rgba(79, 140, 255, 0.2);
  box-shadow: 0 0 0 4px rgba(79, 140, 255, 0.1);
}

.trace-dot.dot-success {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.2);
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.1);
}

.trace-dot.dot-error {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.2);
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1);
}

.trace-line {
  width: 2px;
  height: 12px;
  background: rgba(148, 163, 184, 0.2);
  border-radius: 1px;
}

/* Trace Info */
.trace-info {
  flex: 1;
  min-width: 0;
}

.trace-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.trace-id-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 0.78rem;
  font-weight: 600;
  font-family: "JetBrains Mono", "Fira Code", monospace;
  letter-spacing: 0.02em;
}

.trace-meta-chips {
  display: flex;
  gap: 8px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.meta-chip.events {
  background: rgba(99, 102, 241, 0.1);
  color: #6366f1;
}

.meta-chip.tokens {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.trace-event-preview {
  display: flex;
  gap: 4px;
  margin: 8px 0 4px;
}

.event-type-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  transition: transform 0.2s;
}

.event-type-dot:hover {
  transform: scale(1.5);
}

.dot-llm { background: #6366f1; }
.dot-tool { background: #f59e0b; }
.dot-decision { background: #22c55e; }
.dot-error { background: #ef4444; }
.dot-default { background: #94a3b8; }

.trace-time-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.trace-time {
  font-size: 0.78rem;
  color: #94a3b8;
}

.trace-duration {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 6px;
  background: rgba(79, 140, 255, 0.08);
  color: #4f8cff;
  font-size: 0.72rem;
  font-weight: 700;
}

.trace-expand-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #94a3b8;
  transition: all 0.3s;
}

.trace-expand-icon.rotated {
  transform: rotate(180deg);
  color: #4f8cff;
}

/* ===== Event Nodes ===== */
.trace-events {
  padding: 0 22px 22px 22px;
  margin-left: 28px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}

.event-node {
  display: flex;
  gap: 16px;
  padding-top: 18px;
}

.event-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 22px;
}

.event-dot-outer {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}

.event-dot-inner {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.event-llm .event-dot-outer { background: rgba(99, 102, 241, 0.12); }
.event-llm .event-dot-inner { background: #6366f1; }
.event-tool .event-dot-outer { background: rgba(245, 158, 11, 0.12); }
.event-tool .event-dot-inner { background: #f59e0b; }
.event-decision .event-dot-outer { background: rgba(34, 197, 94, 0.12); }
.event-decision .event-dot-inner { background: #22c55e; }
.event-error .event-dot-outer { background: rgba(239, 68, 68, 0.12); }
.event-error .event-dot-inner { background: #ef4444; }
.event-default .event-dot-outer { background: rgba(148, 163, 184, 0.12); }
.event-default .event-dot-inner { background: #94a3b8; }

.event-connector {
  width: 2px;
  flex: 1;
  min-height: 16px;
  background: rgba(148, 163, 184, 0.16);
  border-radius: 1px;
}

.event-content {
  flex: 1;
  min-width: 0;
  padding-bottom: 8px;
}

.event-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.event-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: 8px;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.badge-llm { background: rgba(99, 102, 241, 0.1); color: #6366f1; }
.badge-tool { background: rgba(245, 158, 11, 0.1); color: #b45309; }
.badge-decision { background: rgba(34, 197, 94, 0.1); color: #15803d; }
.badge-error { background: rgba(239, 68, 68, 0.1); color: #dc2626; }
.badge-default { background: rgba(148, 163, 184, 0.1); color: #475569; }

.event-time {
  font-size: 0.75rem;
  color: #94a3b8;
  font-family: "JetBrains Mono", monospace;
}

.event-body {
  margin-bottom: 8px;
}

.event-data-preview {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.03);
  border: 1px solid rgba(148, 163, 184, 0.1);
  cursor: pointer;
  transition: all 0.2s;
}

.event-data-preview:hover {
  background: rgba(79, 140, 255, 0.04);
  border-color: rgba(79, 140, 255, 0.16);
}

.data-text {
  font-size: 0.82rem;
  color: #334155;
  line-height: 1.5;
  font-family: "JetBrains Mono", monospace;
  word-break: break-all;
}

.expand-hint {
  flex-shrink: 0;
  font-size: 0.72rem;
  font-weight: 600;
  color: #4f8cff;
}

.event-data-full {
  margin-top: 8px;
  padding: 16px;
  border-radius: 12px;
  background: #0f172a;
  color: #dbeafe;
  font-size: 0.78rem;
  line-height: 1.7;
  font-family: "JetBrains Mono", monospace;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
}

/* ===== Token Bar ===== */
.token-bar {
  padding: 8px 14px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.03);
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.token-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.token-label {
  font-size: 0.72rem;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.token-value {
  font-size: 0.75rem;
  font-weight: 600;
  color: #475569;
  font-family: "JetBrains Mono", monospace;
}

.token-progress {
  display: flex;
  height: 4px;
  border-radius: 2px;
  background: rgba(148, 163, 184, 0.1);
  overflow: hidden;
  gap: 1px;
}

.token-progress-input {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, #6366f1, #818cf8);
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.token-progress-output {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ===== Empty State ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 24px;
  text-align: center;
}

.empty-icon {
  width: 100px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(79, 140, 255, 0.08), rgba(99, 102, 241, 0.05));
  color: #94a3b8;
  margin-bottom: 20px;
}

.empty-state h4 {
  font-size: 1.1rem;
  font-weight: 700;
  color: #334155;
  margin-bottom: 8px;
}

.empty-state p {
  font-size: 0.88rem;
  color: #94a3b8;
  max-width: 360px;
}

/* ===== Transitions ===== */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-down-enter-to,
.slide-down-leave-from {
  opacity: 1;
  max-height: 2000px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.trace-list-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.trace-list-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.trace-list-leave-active {
  transition: all 0.3s;
}

.trace-list-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: 1fr;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-inputs {
    flex-direction: column;
  }

  .filter-input,
  .filter-select {
    width: 100%;
  }

  .trace-card-header {
    padding: 14px 16px;
  }

  .trace-events {
    margin-left: 12px;
    padding: 0 16px 16px;
  }

  .trace-meta-chips {
    display: none;
  }
}
</style>
