<template>
  <span class="status-dot" :class="'status-dot--' + status" />
</template>

<script setup>
defineProps({
  status: { type: String, default: 'checking', validator: v => ['healthy', 'degraded', 'checking'].includes(v) },
})
</script>

<style scoped>
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot--healthy {
  background: #22c55e;
}

.status-dot--degraded {
  background: #ef4444;
}

.status-dot--checking {
  background: #9ca3af;
}
</style>
