<template>
  <div>
    <h1 class="page-title">Agent 智能日志</h1>
    <p class="page-subtitle">审计模型调用、工具执行与 trace 级链路信息</p>

    <LogStatsRow
      :stats="auditStats"
      :total-tokens="totalTokens"
      :data-processed="dataProcessed"
      :log-count="totalLogCount"
    />

    <LogFilters
      :filters="filters"
      @search="fetchLogs(); fetchStats()"
      @reset="handleReset"
    />

    <div class="timeline-section" v-loading="loading">
      <div class="section-header">
        <h2 class="section-title">Trace 链路时间线</h2>
        <span class="trace-count">{{ groupedLogs.length }} traces</span>
      </div>

      <TransitionGroup name="trace-list" tag="div" class="trace-list">
        <TraceCard
          v-for="group in groupedLogs"
          :key="group.trace_id"
          :group="group"
          :expanded="expandedTraces.includes(group.trace_id)"
          :expanded-events="expandedEvents"
          @toggle="toggleTrace(group.trace_id)"
          @toggle-event-detail="toggleEventDetail"
        />
      </TransitionGroup>

      <EmptyState
        v-if="!loading && groupedLogs.length === 0"
        title="暂无审计日志"
        description="当 AI 分析任务运行后，链路追踪日志将在此展示"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAgentLogs } from '../composables/useAgentLogs.js'
import LogStatsRow from '../components/agent-log/LogStatsRow.vue'
import LogFilters from '../components/agent-log/LogFilters.vue'
import TraceCard from '../components/agent-log/TraceCard.vue'
import EmptyState from '../components/common/EmptyState.vue'

const route = useRoute()

const {
  filters,
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
  fetchLogs,
  fetchStats,
  handleReset,
} = useAgentLogs()

onMounted(() => {
  fetchLogs()
  fetchStats()
})

watch(
  () => route.query,
  (query) => {
    filters.value.trace_id = typeof query.trace_id === 'string' ? query.trace_id : ''
    filters.value.days = Number(query.days || filters.value.days || 7)
    fetchLogs()
    fetchStats()
  }
)
</script>

<style scoped>
.timeline-section {
  padding: 28px;
  border: 1px solid var(--border, rgba(0, 0, 0, 0.08));
  border-radius: var(--radius-lg, 12px);
  background: var(--bg-primary, #fff);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
  margin: 0;
}

.trace-count {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: var(--radius-full, 999px);
  background: rgba(59, 130, 246, 0.08);
  color: var(--accent, #3b82f6);
  font-size: 0.78rem;
  font-weight: 700;
}

.trace-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Transitions */
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
</style>
