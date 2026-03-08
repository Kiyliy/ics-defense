<template>
  <div class="dashboard-view">
    <div class="page-header">
      <div class="page-header-copy">
        <h2>指挥面板</h2>
        <p class="page-subtitle">
          面向工业控制防御场景的统一态势入口，聚合风险告警、处置待办、攻击链与趋势分析，帮助值守团队更快完成判断与响应。
        </p>
      </div>
      <div class="page-header-meta">
        <span>Threat Posture · Live</span>
        <span>24/7 Security Operations</span>
      </div>
    </div>

    <!-- Stat Cards Grid -->
    <div class="dash-stats">
      <StatCard
        v-for="card in statCards"
        :key="card.label"
        :label="card.label"
        :value="card.value"
        :icon="card.icon"
        :color="card.color"
        :description="card.description"
      />
    </div>

    <!-- Main Content Grid -->
    <div class="dash-content">
      <!-- Trend Chart Section -->
      <section class="dash-panel dash-panel--trend">
        <div class="dash-panel__header">
          <div class="dash-panel__title-group">
            <div class="dash-panel__icon dash-panel__icon--blue">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            </div>
            <div>
              <h3 class="dash-panel__title">7日告警趋势</h3>
              <p class="dash-panel__subtitle">Trend Intelligence · Last 7 Days</p>
            </div>
          </div>
        </div>
        <div ref="chartRef" class="dash-chart"></div>
      </section>

      <!-- Severity Distribution -->
      <section class="dash-panel dash-panel--severity">
        <div class="dash-panel__header">
          <div class="dash-panel__title-group">
            <div class="dash-panel__icon dash-panel__icon--purple">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/>
              </svg>
            </div>
            <div>
              <h3 class="dash-panel__title">严重等级分布</h3>
              <p class="dash-panel__subtitle">Severity Breakdown</p>
            </div>
          </div>
        </div>
        <div class="severity-dist">
          <div class="severity-bar">
            <div
              v-for="seg in severitySegments"
              :key="seg.label"
              class="severity-bar__seg"
              :style="{ width: seg.pct + '%', background: seg.color }"
              :title="seg.label + ': ' + seg.count"
            ></div>
          </div>
          <div class="severity-legend">
            <div v-for="seg in severitySegments" :key="'l-' + seg.label" class="severity-legend__item">
              <span class="severity-legend__dot" :style="{ background: seg.color }"></span>
              <span class="severity-legend__label">{{ seg.label }}</span>
              <span class="severity-legend__val">{{ seg.count }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Recent Alerts Section -->
      <section class="dash-panel dash-panel--alerts">
        <div class="dash-panel__header">
          <div class="dash-panel__title-group">
            <div class="dash-panel__icon dash-panel__icon--red">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
            </div>
            <div>
              <h3 class="dash-panel__title">最近告警</h3>
              <p class="dash-panel__subtitle">Recent Alert Events</p>
            </div>
          </div>
          <button class="dash-link-btn" @click="$router.push('/alerts')">
            查看全部
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14"/><path d="M12 5l7 7-7 7"/>
            </svg>
          </button>
        </div>
        <div class="alert-list">
          <div
            v-for="alert in recentAlerts"
            :key="alert.id"
            class="alert-item"
          >
            <div class="alert-item__bar" :style="{ background: severityColor(alert.severity) }"></div>
            <div class="alert-item__body">
              <div class="alert-item__top">
                <span class="alert-item__id">#{{ alert.id }}</span>
                <span class="alert-item__title">{{ alert.title }}</span>
              </div>
              <div class="alert-item__meta">
                <span class="alert-chip" :style="chipStyle(alert.severity)">
                  {{ alert.severity }}
                </span>
                <span class="alert-chip alert-chip--source">{{ alert.source }}</span>
                <span v-if="alert.src_ip" class="alert-chip alert-chip--ip">{{ alert.src_ip }}</span>
                <span
                  class="alert-chip"
                  :class="alert.status === 'open' ? 'alert-chip--open' : 'alert-chip--closed'"
                >
                  {{ alert.status }}
                </span>
                <span class="alert-item__time">{{ alert.created_at }}</span>
              </div>
            </div>
          </div>
          <div v-if="!recentAlerts.length" class="alert-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
            <p>暂无告警数据</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { getSeverityTagType } from '../utils/ui.js'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { init, graphic } from 'echarts/core'
import StatCard from '../components/StatCard.vue'
import { getDashboardStats, getDashboardTrend, getAlerts } from '../api'
import { buildTrendSeries } from '../api/view-models.js'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const stats = ref({
  total_alerts: 0,
  high_alerts: 0,
  chains: 0,
  pending_approvals: 0,
})

const trendData = ref([])
const recentAlerts = ref([])
const chartRef = ref(null)
let chartInstance = null
let resizeRaf = 0

const statCards = computed(() => {
  const s = stats.value || {}
  return [
    { label: '总告警数', value: s.total_alerts ?? 0, icon: 'Bell', color: '#4f8cff', description: '统一汇聚的安全事件总量' },
    { label: '高危告警', value: s.high_alerts ?? 0, icon: 'Warning', color: '#ef4444', description: '需优先处理的高风险事件' },
    { label: '攻击链', value: s.chains ?? 0, icon: 'Connection', color: '#f59e0b', description: '已串联的攻击活动上下文' },
    { label: '待审批', value: s.pending_approvals ?? 0, icon: 'Checked', color: '#22c55e', description: '等待人工确认的关键动作' },
  ]
})

// Severity distribution computed from stats
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
  ].filter(s => s.count > 0)
})

function severityColor(severity) {
  const map = { critical: '#ef4444', high: '#ef4444', medium: '#f59e0b', low: '#22c55e', info: '#4f8cff' }
  return map[severity] || '#94a3b8'
}

function chipStyle(severity) {
  const c = severityColor(severity)
  return { background: c + '14', color: c, borderColor: c + '30' }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = init(chartRef.value)
  }

  const { labels, counts } = buildTrendSeries(trendData.value)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(9, 20, 36, 0.94)',
      borderColor: 'rgba(96, 165, 250, 0.2)',
      textStyle: { color: '#e2e8f0' },
    },
    grid: { left: 24, right: 16, top: 20, bottom: 20, containLabel: true },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#dbe3ef' } },
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.18)' } },
    },
    series: [
      {
        name: '告警数',
        type: 'line',
        data: counts,
        smooth: true,
        symbolSize: 8,
        areaStyle: {
          color: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(79, 140, 255, 0.28)' },
            { offset: 1, color: 'rgba(79, 140, 255, 0.02)' },
          ]),
        },
        lineStyle: { color: '#2563eb', width: 3 },
        itemStyle: { color: '#4f8cff' },
      },
    ],
  })
}

function handleResize() {
  if (!chartInstance) return
  cancelAnimationFrame(resizeRaf)
  resizeRaf = requestAnimationFrame(() => chartInstance?.resize())
}

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

  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(resizeRaf)
  chartInstance?.dispose()
  chartInstance = null
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
/* ── Stat Cards Grid ────────────────────────── */
.dash-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

@media (max-width: 1200px) {
  .dash-stats { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .dash-stats { grid-template-columns: 1fr; }
}

/* ── Content Layout ─────────────────────────── */
.dash-content {
  display: grid;
  grid-template-columns: 1fr 320px;
  grid-template-rows: auto auto;
  gap: 24px;
}

.dash-panel--trend {
  grid-column: 1 / 2;
  grid-row: 1 / 2;
}

.dash-panel--severity {
  grid-column: 2 / 3;
  grid-row: 1 / 2;
}

.dash-panel--alerts {
  grid-column: 1 / -1;
  grid-row: 2 / 3;
}

@media (max-width: 1024px) {
  .dash-content {
    grid-template-columns: 1fr;
  }
  .dash-panel--trend,
  .dash-panel--severity,
  .dash-panel--alerts {
    grid-column: 1 / -1;
    grid-row: auto;
  }
}

/* ── Panel Base ─────────────────────────────── */
.dash-panel {
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--app-radius-md);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--app-shadow-soft);
  backdrop-filter: blur(16px);
  overflow: hidden;
  transition: box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.dash-panel:hover {
  box-shadow:
    0 16px 40px rgba(15, 23, 42, 0.1),
    0 4px 12px rgba(15, 23, 42, 0.04);
}

.dash-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.dash-panel__title-group {
  display: flex;
  align-items: center;
  gap: 14px;
}

.dash-panel__icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
}

.dash-panel__icon--blue {
  background: linear-gradient(135deg, #4f8cff, #2563eb);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.22);
}

.dash-panel__icon--red {
  background: linear-gradient(135deg, #fb7185, #ef4444);
  box-shadow: 0 6px 16px rgba(239, 68, 68, 0.22);
}

.dash-panel__icon--purple {
  background: linear-gradient(135deg, #a78bfa, #7c3aed);
  box-shadow: 0 6px 16px rgba(124, 58, 237, 0.22);
}

.dash-panel__title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.3;
}

.dash-panel__subtitle {
  font-size: 0.75rem;
  font-weight: 600;
  color: #94a3b8;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-top: 2px;
}

/* ── Link Button ────────────────────────────── */
.dash-link-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid rgba(79, 140, 255, 0.2);
  border-radius: 999px;
  background: rgba(79, 140, 255, 0.08);
  color: var(--app-primary-strong);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.dash-link-btn:hover {
  background: rgba(79, 140, 255, 0.14);
  border-color: rgba(79, 140, 255, 0.35);
  transform: translateX(2px);
}

/* ── Chart ──────────────────────────────────── */
.dash-chart {
  height: 380px;
  min-height: 320px;
  padding: 16px 24px 24px;
}

/* ── Severity Distribution ──────────────────── */
.severity-dist {
  padding: 24px;
}

.severity-bar {
  display: flex;
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  gap: 2px;
  margin-bottom: 20px;
}

.severity-bar__seg {
  min-width: 4px;
  border-radius: 999px;
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.severity-legend {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.severity-legend__item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.85rem;
}

.severity-legend__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.severity-legend__label {
  color: #475569;
  font-weight: 500;
}

.severity-legend__val {
  margin-left: auto;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}

/* ── Alert List ─────────────────────────────── */
.alert-list {
  padding: 8px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-item {
  display: flex;
  align-items: stretch;
  gap: 0;
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.1);
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.alert-item:hover {
  background: rgba(248, 250, 252, 1);
  border-color: rgba(148, 163, 184, 0.2);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}

.alert-item__bar {
  width: 4px;
  flex-shrink: 0;
  border-radius: 4px 0 0 4px;
}

.alert-item__body {
  flex: 1;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.alert-item__top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.alert-item__id {
  font-size: 0.75rem;
  font-weight: 700;
  color: #94a3b8;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.alert-item__title {
  font-size: 0.88rem;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alert-item__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.alert-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  border: 1px solid transparent;
  text-transform: capitalize;
}

.alert-chip--source {
  background: rgba(79, 140, 255, 0.1);
  color: #2563eb;
  border-color: rgba(79, 140, 255, 0.18);
}

.alert-chip--ip {
  background: rgba(148, 163, 184, 0.1);
  color: #475569;
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 0.7rem;
  letter-spacing: -0.02em;
}

.alert-chip--open {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.2);
}

.alert-chip--closed {
  background: rgba(148, 163, 184, 0.1);
  color: #64748b;
  border-color: rgba(148, 163, 184, 0.18);
}

.alert-item__time {
  margin-left: auto;
  font-size: 0.72rem;
  color: #94a3b8;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.alert-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 24px;
  color: #94a3b8;
  font-size: 0.88rem;
}
</style>
