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

    <el-row :gutter="18" class="stats-row">
      <el-col :xs="24" :sm="12" :xl="6" v-for="card in statCards" :key="card.label">
        <StatCard
          :label="card.label"
          :value="card.value"
          :icon="card.icon"
          :color="card.color"
          :description="card.description"
        />
      </el-col>
    </el-row>

    <div class="dashboard-grid">
      <el-card shadow="hover" class="trend-card">
        <template #header>
          <div class="section-title">
            <span>近 7 天告警趋势</span>
            <small>Trend Intelligence</small>
          </div>
        </template>
        <div ref="chartRef" class="trend-chart"></div>
      </el-card>

      <el-card shadow="hover" class="recent-card">
        <template #header>
          <div class="section-title">
            <span>最近告警</span>
            <el-button text type="primary" @click="$router.push('/alerts')">
              查看全部
            </el-button>
          </div>
        </template>
        <el-table :data="recentAlerts" stripe class="data-table">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="title" label="告警标题" min-width="240" show-overflow-tooltip />
          <el-table-column prop="severity" label="等级" width="110">
            <template #default="{ row }">
              <el-tag :type="getSeverityTagType(row.severity)" size="small">
                {{ row.severity }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="120" />
          <el-table-column prop="src_ip" label="源IP" width="140" />
          <el-table-column prop="status" label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.status === 'open' ? 'danger' : 'info'" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="180" />
        </el-table>
      </el-card>
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
.stats-row {
  margin-bottom: 20px;
}

.trend-chart {
  height: 360px;
}

.dashboard-grid {
  grid-template-columns: minmax(0, 1fr);
}
</style>
