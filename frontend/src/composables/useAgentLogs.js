import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { getAuditLogs, getAuditStats } from '../api'
import { filterAuditLogsByDays } from '../api/view-models.js'

// --- Pure helper functions (no reactive state needed) ---

export function shortTraceId(id) {
  if (!id || id === 'unknown') return 'unknown'
  return id.slice(0, 8) + '...'
}

export function traceStatusClass(group) {
  const types = group.eventTypes
  if (types.includes('error')) return 'dot-error'
  if (types.includes('analysis_finished') || types.includes('decision_made')) return 'dot-success'
  return 'dot-active'
}

export function eventTypeCategory(type) {
  if (type.includes('error')) return 'error'
  if (type.includes('llm') || type.includes('plan')) return 'llm'
  if (type.includes('tool')) return 'tool'
  if (type.includes('decision') || type.includes('finished')) return 'decision'
  return 'default'
}

export function eventTypeLabel(type) {
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

export function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr.replace(' ', 'T'))
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatEventTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr.replace(' ', 'T'))
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function calcDuration(start, end) {
  if (!start || !end) return ''
  const ms = new Date(end.replace(' ', 'T')) - new Date(start.replace(' ', 'T'))
  if (ms < 1000) return ''
  if (ms < 60000) return Math.round(ms / 1000) + 's'
  return Math.round(ms / 60000) + 'min'
}

export function formatNumber(n) {
  if (!n) return '0'
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

export function truncateData(data) {
  const str = typeof data === 'string' ? data : JSON.stringify(data)
  return str.length > 80 ? str.slice(0, 80) + '...' : str
}

export function dataLength(data) {
  const str = typeof data === 'string' ? data : JSON.stringify(data)
  return str.length
}

export function formatData(data) {
  try {
    const obj = typeof data === 'string' ? JSON.parse(data) : data
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(data)
  }
}

export function parseTokens(usage) {
  if (!usage) return null
  if (typeof usage === 'object') return usage
  try {
    return JSON.parse(usage)
  } catch {
    return null
  }
}

export function formatTokenUsage(usage) {
  const t = parseTokens(usage)
  if (!t) return String(usage)
  const inp = t.input_tokens || t.prompt_tokens || 0
  const out = t.output_tokens || t.completion_tokens || 0
  return `${formatNumber(inp)} in / ${formatNumber(out)} out`
}

export function tokenInputPct(usage, max) {
  const t = parseTokens(usage)
  if (!t || !max) return 0
  return Math.min(100, ((t.input_tokens || t.prompt_tokens || 0) / max) * 100)
}

export function tokenOutputPct(usage, max) {
  const t = parseTokens(usage)
  if (!t || !max) return 0
  return Math.min(100, ((t.output_tokens || t.completion_tokens || 0) / max) * 100)
}

// --- Composable (reactive state + API) ---

export function useAgentLogs() {
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
        map[tid] = {
          trace_id: tid,
          events: [],
          earliest: log.created_at,
          latest: log.created_at,
          totalTokens: 0,
          maxTokens: 0,
          eventTypes: new Set(),
        }
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
      .map((g) => {
        g.eventTypes = [...g.eventTypes]
        g.duration = calcDuration(g.earliest, g.latest)
        return g
      })
      .sort((a, b) => (b.earliest > a.earliest ? 1 : -1))
  })

  const totalLogCount = computed(() => logs.value.length)

  const dataProcessed = computed(() =>
    logs.value.filter((l) => (l.event_type || '').includes('tool')).length
  )

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

  return {
    filters,
    logs,
    auditStats,
    loading,
    expandedTraces,
    expandedEvents,
    totalTokens,
    groupedLogs,
    totalLogCount,
    dataProcessed,
    toggleTrace,
    toggleEventDetail,
    isEventExpanded,
    fetchLogs,
    fetchStats,
    handleReset,
  }
}
