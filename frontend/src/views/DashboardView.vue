<template>
  <div>
    <div class="page-header">
      <h2>指挥面板</h2>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :xs="12" :sm="6" v-for="card in statCards" :key="card.label">
        <StatCard
          :label="card.label"
          :value="card.value"
          :icon="card.icon"
          :color="card.color"
        />
      </el-col>
    </el-row>

    <!-- 告警趋势图 -->
    <el-card shadow="hover" style="margin-bottom: 20px">
      <template #header>
        <span style="font-weight: 600">24 小时告警趋势</span>
      </template>
      <div ref="chartRef" style="height: 320px"></div>
    </el-card>

    <!-- 最近告警列表 -->
    <el-card shadow="hover">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">最近告警</span>
          <el-button text type="primary" @click="$router.push('/alerts')">
            查看全部
          </el-button>
        </div>
      </template>
      <el-table :data="recentAlerts" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="告警标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="severity" label="等级" width="100">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="src_ip" label="源IP" width="140" />
        <el-table-column prop="status" label="状态" width="100">
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
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { init, graphic } from 'echarts/core'
import StatCard from '../components/StatCard.vue'
import { getDashboardStats, getDashboardTrend, getAlerts } from '../api'

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

const statCards = computed(() => {
  const s = stats.value || {}
  return [
    { label: '总告警数', value: s.total_alerts ?? 0, icon: 'Bell', color: '#409eff' },
    { label: '高危告警', value: s.high_alerts ?? 0, icon: 'Warning', color: '#f56c6c' },
    { label: '攻击链', value: s.chains ?? 0, icon: 'Connection', color: '#e6a23c' },
    { label: '待审批', value: s.pending_approvals ?? 0, icon: 'Checked', color: '#67c23a' },
  ]
})

function severityType(severity) {
  const map = { critical: 'danger', high: 'warning', medium: '', low: 'info' }
  return map[severity] || 'info'
}

function renderChart() {
  if (!chartRef.value) return
  chartInstance = init(chartRef.value)

  const hours = trendData.value.map((d) => d.hour)
  const counts = trendData.value.map((d) => d.count)

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 30, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: hours,
      axisLabel: { color: '#8c8c8c' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#8c8c8c' },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [
      {
        name: '告警数',
        type: 'line',
        data: counts,
        smooth: true,
        areaStyle: {
          color: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64,158,255,0.3)' },
            { offset: 1, color: 'rgba(64,158,255,0.02)' },
          ]),
        },
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
      },
    ],
  })
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(async () => {
  try {
    const [statsRes, trendRes, alertsRes] = await Promise.all([
      getDashboardStats(),
      getDashboardTrend(),
      getAlerts({ page: 1, limit: 10 }),
    ])

    // Map backend response structure to frontend stats shape
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
  chartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>
