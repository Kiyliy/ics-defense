<template>
  <div class="stats-row">
    <StatCard
      label="分析次数"
      :value="stats.total_analyses || 0"
      icon="DataAnalysis"
      color="#6366f1"
    />
    <StatCard
      label="Token 消耗"
      :value="totalTokens"
      icon="Clock"
      color="#f59e0b"
      :description="tokenDesc"
    />
    <StatCard
      label="数据处理量"
      :value="dataProcessed"
      icon="Connection"
      color="#3b82f6"
    />
    <StatCard
      label="日志条数"
      :value="logCount"
      icon="Document"
      color="#22c55e"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StatCard from '../StatCard.vue'

const props = defineProps({
  stats: { type: Object, default: () => ({}) },
  totalTokens: { type: Number, default: 0 },
  dataProcessed: { type: Number, default: 0 },
  logCount: { type: Number, default: 0 },
})

function fmt(n) {
  if (!n) return '0'
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

const tokenDesc = computed(() => {
  const inp = props.stats.total_input_tokens
  if (!inp) return ''
  return `IN ${fmt(inp)} / OUT ${fmt(props.stats.total_output_tokens || 0)}`
})
</script>

<style scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

@media (max-width: 900px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>
