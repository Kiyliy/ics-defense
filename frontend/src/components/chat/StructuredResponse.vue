<template>
  <div class="ai-structured">
    <!-- Analysis -->
    <div class="ai-analysis" v-if="parsed.analysis" v-html="renderMarkdown(parsed.analysis)"></div>

    <!-- Risk & confidence tags -->
    <div class="ai-tags" v-if="parsed.risk_level || parsed.confidence || parsed.action_type">
      <span v-if="parsed.risk_level" :class="['ai-tag', `ai-tag--${(parsed.risk_level || '').toLowerCase()}`]">
        <svg viewBox="0 0 12 12" width="12" height="12"><path d="M6 1L1 11h10L6 1z" stroke="currentColor" stroke-width="1.2" fill="none"/></svg>
        风险: {{ parsed.risk_level }}
      </span>
      <span v-if="parsed.confidence" class="ai-tag ai-tag--info">
        <svg viewBox="0 0 12 12" width="12" height="12"><circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.2" fill="none"/><path d="M6 4v3M6 8.5v.01" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
        置信度: {{ parsed.confidence }}
      </span>
      <span v-if="parsed.action_type" class="ai-tag ai-tag--warning">
        <svg viewBox="0 0 12 12" width="12" height="12"><path d="M1 6l4 4L11 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
        动作: {{ parsed.action_type }}
      </span>
    </div>

    <!-- MITRE fields card -->
    <div class="mitre-card" v-if="parsed.mitre_tactic || parsed.mitre_technique">
      <div class="mitre-card__header">
        <svg viewBox="0 0 16 16" width="14" height="14"><rect x="1" y="1" width="6" height="6" rx="1" fill="currentColor"/><rect x="9" y="1" width="6" height="6" rx="1" fill="currentColor"/><rect x="1" y="9" width="6" height="6" rx="1" fill="currentColor"/><rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor"/></svg>
        MITRE ATT&amp;CK
      </div>
      <div v-if="parsed.mitre_tactic" class="mitre-card__field">
        <span class="mitre-card__label">战术 Tactic</span>
        <span class="mitre-card__value">{{ parsed.mitre_tactic }}</span>
      </div>
      <div v-if="parsed.mitre_technique" class="mitre-card__field">
        <span class="mitre-card__label">技术 Technique</span>
        <span class="mitre-card__value">{{ parsed.mitre_technique }}</span>
      </div>
    </div>

    <!-- Rationale -->
    <div v-if="parsed.rationale" class="rationale-block">
      <span class="rationale-block__label">
        <svg viewBox="0 0 12 12" width="12" height="12"><path d="M6 1a5 5 0 110 10A5 5 0 016 1z" stroke="currentColor" stroke-width="1.2" fill="none"/><path d="M6 4v3M6 8.5v.01" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
        依据
      </span>
      <p>{{ parsed.rationale }}</p>
    </div>

    <!-- Recommendation card -->
    <div v-if="parsed.recommendation" class="recommendation-card">
      <div class="recommendation-card__icon">
        <svg viewBox="0 0 16 16" width="18" height="18"><path d="M8 1l2 5h5l-4 3 1.5 5L8 11l-4.5 3L5 9 1 6h5l2-5z" stroke="#16a34a" stroke-width="1.3" fill="rgba(34,197,94,0.15)"/></svg>
      </div>
      <div class="recommendation-card__body">
        <span class="recommendation-card__title">建议 Recommendation</span>
        <p>{{ parsed.recommendation }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { renderMarkdownSafe } from '../../api/markdown.js'

defineProps({
  parsed: { type: Object, required: true },
})

function renderMarkdown(text) {
  return renderMarkdownSafe(text)
}
</script>

<style scoped>
.ai-structured {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-analysis {
  line-height: 1.8;
}

/* Tags */
.ai-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ai-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.ai-tag--critical,
.ai-tag--high {
  background: rgba(239, 68, 68, 0.08);
  color: #dc2626;
}

.ai-tag--medium,
.ai-tag--warning {
  background: rgba(245, 158, 11, 0.08);
  color: #d97706;
}

.ai-tag--low {
  background: rgba(34, 197, 94, 0.08);
  color: #16a34a;
}

.ai-tag--info {
  background: rgba(59, 130, 246, 0.08);
  color: #2563eb;
}

/* MITRE card */
.mitre-card {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  border: 1px solid var(--border);
}

.mitre-card__header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2563eb;
  margin-bottom: 10px;
}

.mitre-card__field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
}

.mitre-card__field:not(:last-child) {
  border-bottom: 1px solid var(--border);
}

.mitre-card__label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.mitre-card__value {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Rationale */
.rationale-block {
  padding: 12px 16px;
  border-left: 2px solid var(--border-strong, var(--border));
  background: var(--bg-hover);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
}

.rationale-block__label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.rationale-block p {
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 0;
}

/* Recommendation card */
.recommendation-card {
  display: flex;
  gap: 14px;
  padding: 16px;
  border-radius: var(--radius-md);
  background: rgba(34, 197, 94, 0.04);
  border: 1px solid rgba(34, 197, 94, 0.15);
}

.recommendation-card__icon {
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
  flex-shrink: 0;
}

.recommendation-card__body {
  min-width: 0;
}

.recommendation-card__title {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #16a34a;
  margin-bottom: 6px;
}

.recommendation-card__body p {
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 0;
}
</style>
