<template>
  <div class="page-banner">
    <div class="banner-left">
      <h1 class="banner-title">{{ title }}</h1>
      <span class="banner-divider" />
      <p class="banner-subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.right" class="banner-right">
      <slot name="right" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<style scoped>
.page-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  margin: -24px -24px 20px -24px;
  background: var(--bg-primary, #fff);
  border-bottom: 1px solid var(--border-default, rgba(0, 0, 0, 0.06));
}

.banner-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.banner-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
  white-space: nowrap;
  margin: 0;
  line-height: 1;
}

.banner-divider {
  width: 1px;
  height: 14px;
  background: var(--border-default, rgba(0, 0, 0, 0.15));
  flex-shrink: 0;
}

.banner-subtitle {
  font-size: 0.8rem;
  color: var(--text-muted, #9ca3af);
  margin: 0;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.banner-right {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
  white-space: nowrap;
}
</style>
