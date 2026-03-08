<template>
  <div>
    <h1 class="page-title">仪表盘</h1>
    <p class="page-subtitle">聚合风险告警、处置待办、攻击链与趋势分析</p>

    <div class="stats-grid">
      <StatCard v-for="card in statCards" :key="card.label" v-bind="card" />
    </div>

    <div class="charts-grid">
      <TrendChart :trend-data="trendData" />
      <SeverityChart :segments="severitySegments" />
    </div>

    <RecentAlertsList :alerts="recentAlerts" @view-all="$router.push('/alerts')" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import StatCard from '../components/StatCard.vue'
import TrendChart from '../components/dashboard/TrendChart.vue'
import SeverityChart from '../components/dashboard/SeverityChart.vue'
import RecentAlertsList from '../components/dashboard/RecentAlertsList.vue'
import { getDashboardStats, getDashboardTrend, getAlerts } from '../api'

const stats = ref({
  total_alerts: 0,
  high_alerts: 0,
  chains: 0,
  pending_approvals: 0,
})

const trendData = ref([])
const recentAlerts = ref([])

const statCards = computed(() => {
  const s = stats.value || {}
  return [
    { label: '总告警数', value: s.total_alerts ?? 0, icon: 'Bell', color: '#4f8cff', description: '统一汇聚的安全事件总量' },
    { label: '高危告警', value: s.high_alerts ?? 0, icon: 'Warning', color: '#ef4444', description: '需优先处理的高风险事件' },
    { label: '攻击链', value: s.chains ?? 0, icon: 'Connection', color: '#f59e0b', description: '已串联的攻击活动上下文' },
    { label: '待审批', value: s.pending_approvals ?? 0, icon: 'Checked', color: '#22c55e', description: '等待人工确认的关键动作' },
  ]
})

const severitySegments = computed(() => {
  const s = stats.value || {}
  const total = s.total_alerts || 1
  const high = s.high_alerts || 0
  const pending = s.pending_approvals || 0
  const medium = Math.max(0, Math.floor((total - high - pending) * 0.6))
  const low = Math.max(0, total - high - medium - pending)
  return [
    { label: '高危', count: high, color: '#ef4444', pct: (high / total) * 100 },
    { label: '中危', count: medium, color: '#f59e0b', pct: (medium / total) * 100 },
    { label: '低危', count: low, color: '#22c55e', pct: (low / total) * 100 },
    { label: '待审', count: pending, color: '#8b5cf6', pct: (pending / total) * 100 },
  ].filter(seg => seg.count > 0)
})

onMounted(async () => {
  try {
    const [statsRes, trendRes, alertsRes] = await Promise.all([
      getDashboardStats(),
      getDashboardTrend(),
      getAlerts({ page: 1, limit: 10 }),
    ])

    const summary = statsRes?.summary || {}
    const bySeverity = statsRes?.alertsBySeverity || []
    const highCount = bySeverity
      .filter((s) => s.severity === 'high' || s.severity === 'critical')
      .reduce((sum, s) => sum + (s.count || 0), 0)

    stats.value = {
      total_alerts: summary.totalAlerts ?? 0,
      high_alerts: highCount,
      chains: summary.totalChains ?? 0,
      pending_approvals: summary.pendingDecisions ?? 0,
    }

    trendData.value = trendRes?.trend || []
    recentAlerts.value = alertsRes?.alerts || []
  } catch (err) {
    console.error('Dashboard load error:', err)
  }
})
</script>

<style scoped>
.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.page-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: 24px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
  margin-bottom: 24px;
}
@media (max-width: 1200px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1024px) {
  .charts-grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .stats-grid { grid-template-columns: 1fr; }
}
</style>
