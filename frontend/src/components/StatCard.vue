<template>
  <div class="stat-card" @mouseenter="hovered = true" @mouseleave="hovered = false">
    <!-- Decorative background glow -->
    <div class="stat-card__glow" :style="glowStyle"></div>

    <div class="stat-card__header">
      <div class="stat-card__icon" :style="iconStyle">
        <el-icon :size="26">
          <component :is="icon" />
        </el-icon>
      </div>
      <div class="stat-card__label">{{ label }}</div>
    </div>

    <div class="stat-card__body">
      <div class="stat-card__value">
        <span class="stat-card__number">{{ animatedValue }}</span>
      </div>
      <div v-if="description" class="stat-card__desc">
        <span class="stat-card__desc-dot" :style="{ background: color }"></span>
        {{ description }}
      </div>
    </div>

    <!-- Subtle sparkline decoration -->
    <svg class="stat-card__sparkline" viewBox="0 0 200 40" preserveAspectRatio="none">
      <path :d="sparklinePath" :stroke="color" stroke-width="1.5" fill="none" opacity="0.25" />
      <path :d="sparklineArea" :fill="color" opacity="0.06" />
    </svg>
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

const hovered = ref(false)
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
  background: `linear-gradient(135deg, ${props.color}, ${props.color}bb)`,
  boxShadow: `0 8px 24px ${props.color}33, inset 0 1px 0 rgba(255,255,255,0.28)`,
}))

const glowStyle = computed(() => ({
  background: `radial-gradient(circle at 20% 30%, ${props.color}18, transparent 70%)`,
}))

// Generate a deterministic pseudo-random sparkline based on the label
const sparklinePoints = computed(() => {
  let seed = 0
  for (let i = 0; i < props.label.length; i++) seed += props.label.charCodeAt(i)
  const points = []
  for (let i = 0; i < 8; i++) {
    seed = (seed * 9301 + 49297) % 233280
    points.push(10 + (seed / 233280) * 22)
  }
  return points
})

const sparklinePath = computed(() => {
  const pts = sparklinePoints.value
  const step = 200 / (pts.length - 1)
  return pts.map((y, i) => `${i === 0 ? 'M' : 'L'}${i * step},${y}`).join(' ')
})

const sparklineArea = computed(() => {
  const pts = sparklinePoints.value
  const step = 200 / (pts.length - 1)
  const line = pts.map((y, i) => `${i === 0 ? 'M' : 'L'}${i * step},${y}`).join(' ')
  return `${line} L200,40 L0,40 Z`
})
</script>

<style scoped>
.stat-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 164px;
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.66);
  border-radius: 22px;
  background:
    radial-gradient(circle at top right, rgba(79, 140, 255, 0.08), transparent 50%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.94));
  box-shadow: var(--app-shadow-soft);
  overflow: hidden;
  transition:
    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: default;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow:
    0 20px 48px rgba(15, 23, 42, 0.13),
    0 8px 16px rgba(15, 23, 42, 0.06);
}

.stat-card::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.38), transparent 55%);
  pointer-events: none;
}

.stat-card__glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.stat-card__header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-card__icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.stat-card:hover .stat-card__icon {
  transform: scale(1.06);
}

.stat-card__label {
  font-size: 0.88rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--app-text-muted);
  text-transform: none;
}

.stat-card__body {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.stat-card__number {
  font-size: clamp(2.0rem, 2.2vw, 2.4rem);
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #0f172a;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.stat-card__desc {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.04);
  font-size: 0.75rem;
  font-weight: 500;
  color: #64748b;
  width: fit-content;
  line-height: 1.5;
}

.stat-card__desc-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stat-card__sparkline {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40px;
  pointer-events: none;
  z-index: 0;
}
</style>
