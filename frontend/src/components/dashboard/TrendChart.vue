<template>
  <section class="trend-panel">
    <div class="panel-header">
      <h3 class="panel-title">7日告警趋势</h3>
    </div>
    <div ref="chartRef" class="trend-chart"></div>
  </section>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { init, graphic } from 'echarts/core'
import { buildTrendSeries } from '../../api/view-models.js'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  trendData: {
    type: Array,
    default: () => [],
  },
})

const chartRef = ref(null)
let chartInstance = null
let resizeRaf = 0

function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = init(chartRef.value)
  }

  const { labels, counts } = buildTrendSeries(props.trendData)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: 'rgba(0,0,0,0.08)',
      textStyle: { color: '#0a0a0a', fontSize: 13 },
      borderWidth: 1,
      padding: [8, 12],
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

watch(
  () => props.trendData,
  () => renderChart(),
  { deep: true },
)

onMounted(() => {
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
.trend-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
}
.panel-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.panel-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}
.trend-chart {
  height: 360px;
  padding: 16px 20px 20px;
}
</style>
