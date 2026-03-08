<template>
  <div class="evidence-block">
    <template v-if="typeof evidence === 'object' && evidence !== null">
      <div v-for="(val, key) in evidence" :key="key" class="evidence-field">
        <span class="evidence-field__key">{{ key }}</span>
        <span class="evidence-field__val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
      </div>
    </template>
    <p v-else class="evidence-text">{{ evidence }}</p>
  </div>
</template>

<script setup>
defineProps({
  evidence: { type: [Object, String], default: null }
})
</script>

<style scoped>
.evidence-block {
  padding: 16px;
  border-radius: var(--radius-md, 8px);
  background: var(--bg-page, #f8f9fa);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
}

.evidence-field {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border, rgba(0,0,0,0.08));
  font-size: 0.84rem;
}

.evidence-field:last-child {
  border-bottom: none;
}

.evidence-field__key {
  font-weight: 700;
  color: var(--text-secondary, #6b7280);
  min-width: 120px;
  flex-shrink: 0;
  text-transform: capitalize;
}

.evidence-field__val {
  color: var(--text-primary, #0a0a0a);
  word-break: break-word;
}

.evidence-text {
  font-size: 0.88rem;
  color: var(--text-secondary, #6b7280);
  line-height: 1.7;
  white-space: pre-wrap;
}
</style>
