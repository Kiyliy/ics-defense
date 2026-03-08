<template>
  <section class="severity-panel">
    <div class="panel-header">
      <h3 class="panel-title">严重等级分布</h3>
    </div>
    <div class="severity-body">
      <div class="severity-bar">
        <div
          v-for="seg in segments"
          :key="seg.label"
          class="severity-bar__seg"
          :style="{ width: seg.pct + '%', background: seg.color }"
          :title="seg.label + ': ' + seg.count"
        ></div>
      </div>
      <div class="severity-legend">
        <div
          v-for="seg in segments"
          :key="'l-' + seg.label"
          class="severity-legend__item"
        >
          <span class="severity-legend__dot" :style="{ background: seg.color }"></span>
          <span class="severity-legend__label">{{ seg.label }}</span>
          <span class="severity-legend__val">{{ seg.count }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  segments: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.severity-panel {
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
.severity-body {
  padding: 20px;
}
.severity-bar {
  display: flex;
  height: 8px;
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
  color: var(--text-secondary);
  font-weight: 500;
}
.severity-legend__val {
  margin-left: auto;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
</style>
