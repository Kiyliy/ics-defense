<template>
  <div class="stat-card">
    <div class="icon-wrapper" :style="{ background: color }">
      <el-icon :size="28">
        <component :is="icon" />
      </el-icon>
    </div>
    <div class="info">
      <div class="label">{{ label }}</div>
      <div class="value">{{ value }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: 0 },
  icon: { type: String, required: true },
  color: { type: String, default: '#409eff' },
})
</script>
