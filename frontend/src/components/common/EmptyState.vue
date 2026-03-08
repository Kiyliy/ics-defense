<template>
  <div class="empty-state">
    <div class="empty-state__icon">
      <slot name="icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <path d="M12 8v4m0 4h.01"/>
        </svg>
      </slot>
    </div>
    <h3 class="empty-state__title">{{ title }}</h3>
    <p class="empty-state__desc" v-if="description">{{ description }}</p>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '' },
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  max-width: 360px;
  margin: 0 auto;
  padding: 48px 24px;
}

.empty-state__icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.empty-state__title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.empty-state__desc {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}
</style>
