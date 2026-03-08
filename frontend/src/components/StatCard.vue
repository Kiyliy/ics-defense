<template>
  <div class="stat-card">
    <div class="icon-wrapper" :style="iconStyle">
      <el-icon :size="28">
        <component :is="icon" />
      </el-icon>
    </div>
    <div class="info">
      <div class="label">{{ label }}</div>
      <div class="value">{{ value }}</div>
      <div v-if="description" class="description">{{ description }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: 0 },
  icon: { type: String, required: true },
  color: { type: String, default: '#409eff' },
  description: { type: String, default: '' },
})

const iconStyle = computed(() => ({
  background: `linear-gradient(135deg, ${props.color}, ${props.color}cc)`,
}))
</script>

<style scoped>
.description {
  margin-top: 8px;
  font-size: 0.82rem;
  color: #64748b;
}
</style>
