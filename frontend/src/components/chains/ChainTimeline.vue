<template>
  <div class="timeline">
    <div v-for="(stg, i) in stages" :key="i" class="timeline__step">
      <div class="timeline__dot"></div>
      <div class="timeline__content">
        <span class="timeline__label">{{ stg.name || stg }}</span>
        <span class="timeline__time" v-if="stg.time">{{ stg.time }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  stages: { type: Array, default: () => [] }
})
</script>

<style scoped>
.timeline {
  display: flex;
  gap: 0;
  align-items: flex-start;
  overflow-x: auto;
  padding: 8px 0;
}

.timeline__step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-width: 100px;
  position: relative;
  flex: 1;
}

.timeline__step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 7px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, var(--accent, #3b82f6), rgba(59, 130, 246, 0.3));
}

.timeline__dot {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-full, 999px);
  background: var(--accent, #3b82f6);
  position: relative;
  z-index: 1;
}

.timeline__content {
  text-align: center;
}

.timeline__label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary, #6b7280);
  display: block;
}

.timeline__time {
  font-size: 0.7rem;
  color: var(--text-muted, #9ca3af);
}
</style>
