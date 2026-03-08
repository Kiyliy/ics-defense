<template>
  <div class="stat-card">
    <div class="stat-card__icon" :style="iconStyle">
      <el-icon :size="20">
        <component :is="icon" />
      </el-icon>
    </div>
    <div class="stat-card__label">{{ label }}</div>
    <div class="stat-card__number">{{ animatedValue }}</div>
    <div v-if="description" class="stat-card__desc">{{ description }}</div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: 0 },
  icon: { type: String, required: true },
  color: { type: String, default: '#4f8cff' },
  description: { type: String, default: '' },
})

const animatedValue = ref(0)
const duration = 800

function animateNumber(from, to) {
  if (typeof to !== 'number') {
    animatedValue.value = to
    return
  }
  const start = performance.now()
  const diff = to - from
  function tick(now) {
    const elapsed = now - start
    const progress = Math.min(elapsed / duration, 1)
    const ease = 1 - Math.pow(1 - progress, 3) // easeOutCubic
    animatedValue.value = Math.round(from + diff * ease)
    if (progress < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

onMounted(() => {
  animateNumber(0, props.value)
})

watch(
  () => props.value,
  (newVal, oldVal) => {
    const from = typeof oldVal === 'number' ? oldVal : 0
    animateNumber(from, newVal)
  }
)

const iconStyle = computed(() => ({
  background: props.color + '14',
  color: props.color,
}))
</script>

<style scoped>
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
  transition: border-color 0.2s var(--ease);
}

.stat-card:hover {
  border-color: var(--border-strong);
}

.stat-card__icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-card__label {
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}

.stat-card__number {
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: var(--text-primary);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.stat-card__desc {
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
