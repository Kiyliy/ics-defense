<template>
  <div :class="['chain-card', { 'chain-card--expanded': expanded }]">
    <!-- Card header area -->
    <div class="chain-card__header" @click="$emit('toggle')">
      <div class="chain-card__top">
        <div class="chain-card__title-row">
          <span class="chain-card__id">#{{ chain.id }}</span>
          <h3 class="chain-card__name">{{ chain.name || '未命名链路' }}</h3>
        </div>
        <span :class="['risk-badge', `risk-badge--${normalizeRisk(chain.risk_level)}`]">
          <svg class="risk-badge__dot" viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>
          {{ chain.risk_level || 'unknown' }}
        </span>
      </div>

      <!-- Confidence bar -->
      <div class="confidence-row" v-if="chain.confidence != null">
        <span class="confidence-label">CONFIDENCE</span>
        <div class="confidence-track">
          <div
            class="confidence-fill"
            :style="{ width: Math.min(100, Math.max(0, Number(chain.confidence) || 0)) + '%' }"
          ></div>
        </div>
        <span class="confidence-value">{{ Math.round(Number(chain.confidence) || 0) }}%</span>
      </div>

      <!-- Meta chips -->
      <div class="chain-card__meta">
        <span class="meta-chip meta-chip--stage" v-if="chain.stage || chain.attack_stage">
          <svg viewBox="0 0 16 16" width="14" height="14"><path d="M8 1l2.5 5 5.5.8-4 3.9.9 5.3L8 13.3 3.1 16l.9-5.3-4-3.9L5.5 6z" fill="currentColor"/></svg>
          {{ chain.stage || chain.attack_stage || 'N/A' }}
        </span>
        <span class="meta-chip meta-chip--mitre" v-if="chain.mitre_technique">
          <svg viewBox="0 0 16 16" width="14" height="14"><rect x="1" y="1" width="6" height="6" rx="1" fill="currentColor"/><rect x="9" y="1" width="6" height="6" rx="1" fill="currentColor"/><rect x="1" y="9" width="6" height="6" rx="1" fill="currentColor"/><rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor"/></svg>
          {{ chain.mitre_technique }}
        </span>
        <span class="meta-chip meta-chip--alerts">
          <svg viewBox="0 0 16 16" width="14" height="14"><path d="M8 1.5L1 14h14L8 1.5z" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M8 7v3M8 11.5v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          {{ chain.alert_count || 0 }} 告警
        </span>
        <span class="meta-chip meta-chip--status">{{ chain.status || 'pending' }}</span>
      </div>

      <!-- Expand indicator -->
      <div class="chain-card__expand-hint">
        <svg :class="['expand-chevron', { 'expand-chevron--open': expanded }]" viewBox="0 0 16 16" width="16" height="16">
          <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
        </svg>
      </div>
    </div>

    <!-- Expanded detail panel -->
    <transition name="expand">
      <div v-if="expanded" class="chain-card__detail">
        <!-- Timeline / Attack stages -->
        <div class="detail-section" v-if="chain.stages && chain.stages.length">
          <h4 class="detail-section__title">
            <svg viewBox="0 0 16 16" width="16" height="16"><circle cx="3" cy="8" r="2" fill="currentColor"/><circle cx="8" cy="8" r="2" fill="currentColor"/><circle cx="13" cy="8" r="2" fill="currentColor"/><line x1="5" y1="8" x2="6" y2="8" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="8" x2="11" y2="8" stroke="currentColor" stroke-width="1.5"/></svg>
            攻击阶段
          </h4>
          <ChainTimeline :stages="chain.stages" />
        </div>

        <!-- Related alerts -->
        <div class="detail-section" v-if="(chain.alerts || []).length">
          <h4 class="detail-section__title">
            <svg viewBox="0 0 16 16" width="16" height="16"><path d="M8 1.5L1 14h14L8 1.5z" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M8 7v3M8 11.5v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
            关联告警
            <span class="detail-section__count">{{ chain.alerts.length }}</span>
          </h4>
          <div class="alert-cards">
            <div v-for="alert in chain.alerts" :key="alert.id" class="alert-mini">
              <span :class="['severity-dot', `severity-dot--${(alert.severity || '').toLowerCase()}`]"></span>
              <div class="alert-mini__body">
                <span class="alert-mini__title">{{ alert.title || 'Alert #' + alert.id }}</span>
                <span class="alert-mini__meta">
                  <span v-if="alert.id">ID: {{ alert.id }}</span>
                  <span v-if="alert.src_ip">{{ alert.src_ip }}</span>
                </span>
              </div>
              <el-tag :type="getSeverityTagType(alert.severity)" size="small">{{ alert.severity }}</el-tag>
            </div>
          </div>
        </div>

        <!-- Evidence -->
        <div class="detail-section" v-if="chain.evidence">
          <h4 class="detail-section__title">
            <svg viewBox="0 0 16 16" width="16" height="16"><path d="M10 1H3a1 1 0 00-1 1v12a1 1 0 001 1h10a1 1 0 001-1V5l-4-4z" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M10 1v4h4" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
            证据 Evidence
          </h4>
          <ChainEvidence :evidence="chain.evidence" />
        </div>

        <!-- Decisions -->
        <div class="detail-section" v-if="(chain.decisions || []).length">
          <h4 class="detail-section__title">
            <svg viewBox="0 0 16 16" width="16" height="16"><path d="M14 2l-8 8-3-3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
            决策 Decisions
          </h4>
          <div class="decision-cards">
            <div v-for="dec in chain.decisions" :key="dec.id" class="decision-card">
              <div class="decision-card__top">
                <span class="decision-card__id">#{{ dec.id }}</span>
                <el-tag :type="getStatusTagType(dec.status)" size="small">{{ dec.status }}</el-tag>
              </div>
              <p class="decision-card__text">{{ dec.recommendation || dec.action_type || '-' }}</p>
              <div v-if="dec.status === 'pending'" class="decision-card__actions">
                <button class="action-btn action-btn--approve" @click.stop="$emit('decide', dec.id, 'accepted')">
                  <svg viewBox="0 0 16 16" width="14" height="14"><path d="M13 4L6 12 3 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                  批准
                </button>
                <button class="action-btn action-btn--reject" @click.stop="$emit('decide', dec.id, 'rejected')">
                  <svg viewBox="0 0 16 16" width="14" height="14"><path d="M12 4L4 12M4 4l8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>
                  拒绝
                </button>
              </div>
              <span v-else class="decision-card__resolved">已处理</span>
            </div>
          </div>
        </div>

        <!-- Created time -->
        <div class="detail-footer" v-if="chain.created_at">
          <svg viewBox="0 0 16 16" width="14" height="14"><circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M8 4v4l3 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
          {{ chain.created_at }}
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { getSeverityTagType, getStatusTagType } from '../../utils/ui.js'
import ChainTimeline from './ChainTimeline.vue'
import ChainEvidence from './ChainEvidence.vue'

defineProps({
  chain: { type: Object, required: true },
  expanded: { type: Boolean, default: false }
})

defineEmits(['toggle', 'decide'])

function normalizeRisk(level) {
  return String(level || 'unknown').toLowerCase()
}
</script>

<style scoped>
.chain-card {
  border: 1px solid var(--border, rgba(0,0,0,0.08));
  border-radius: var(--radius-lg, 12px);
  background: var(--bg-primary, #fff);
  overflow: hidden;
  transition: border-color 0.3s var(--ease, ease);
}

.chain-card:hover {
  border-color: var(--border-strong, rgba(0,0,0,0.15));
}

.chain-card--expanded {
  grid-column: 1 / -1;
  border-color: rgba(59, 130, 246, 0.25);
}

.chain-card__header {
  padding: 24px;
  cursor: pointer;
  transition: background 0.2s var(--ease, ease);
}

.chain-card__header:hover {
  background: var(--bg-hover, #f3f4f6);
}

.chain-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.chain-card__title-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.chain-card__id {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted, #9ca3af);
}

.chain-card__name {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* Risk badge */
.risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--radius-full, 999px);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.risk-badge__dot { width: 8px; height: 8px; }

.risk-badge--critical { background: rgba(239, 68, 68, 0.1); color: #dc2626; }
.risk-badge--high { background: rgba(249, 115, 22, 0.1); color: #ea580c; }
.risk-badge--medium { background: rgba(245, 158, 11, 0.1); color: #d97706; }
.risk-badge--low { background: rgba(34, 197, 94, 0.1); color: #16a34a; }
.risk-badge--unknown, .risk-badge--info { background: rgba(148, 163, 184, 0.1); color: #64748b; }

/* Confidence bar */
.confidence-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.confidence-label {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted, #9ca3af);
  flex-shrink: 0;
}

.confidence-track {
  flex: 1;
  height: 6px;
  border-radius: var(--radius-full, 999px);
  background: rgba(148, 163, 184, 0.12);
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  border-radius: var(--radius-full, 999px);
  background: var(--accent, #3b82f6);
  transition: width 0.6s var(--ease, ease);
}

.confidence-value {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
  min-width: 36px;
  text-align: right;
}

/* Meta chips */
.chain-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: var(--radius-full, 999px);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1;
}

.meta-chip--stage { background: rgba(139, 92, 246, 0.1); color: #7c3aed; }
.meta-chip--mitre { background: rgba(59, 130, 246, 0.1); color: #2563eb; }
.meta-chip--alerts { background: rgba(245, 158, 11, 0.1); color: #d97706; }
.meta-chip--status { background: rgba(148, 163, 184, 0.1); color: #475569; text-transform: capitalize; }

/* Expand indicator */
.chain-card__expand-hint {
  display: flex;
  justify-content: center;
  padding-top: 12px;
  color: var(--text-muted, #9ca3af);
}

.expand-chevron {
  transition: transform 0.3s var(--ease, ease);
}

.expand-chevron--open {
  transform: rotate(180deg);
}

/* Expand transition */
.expand-enter-active { animation: expandIn 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.expand-leave-active { animation: expandIn 0.25s cubic-bezier(0.4, 0, 0.2, 1) reverse; }

@keyframes expandIn {
  from { opacity: 0; max-height: 0; transform: translateY(-8px); }
  to { opacity: 1; max-height: 2000px; transform: translateY(0); }
}

/* Detail panel */
.chain-card__detail {
  padding: 0 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  border-top: 1px solid var(--border, rgba(0,0,0,0.08));
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-section__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
}

.detail-section__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: var(--radius-full, 999px);
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 0.7rem;
  font-weight: 700;
}

/* Alert mini cards */
.alert-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-mini {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md, 8px);
  background: var(--bg-page, #f8f9fa);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
  transition: background 0.2s var(--ease, ease);
}

.alert-mini:hover {
  background: var(--bg-hover, #f3f4f6);
}

.severity-dot { width: 10px; height: 10px; border-radius: var(--radius-full, 999px); flex-shrink: 0; }
.severity-dot--critical { background: #ef4444; }
.severity-dot--high, .severity-dot--error { background: #f97316; }
.severity-dot--medium, .severity-dot--warning { background: #f59e0b; }
.severity-dot--low, .severity-dot--info { background: #22c55e; }

.alert-mini__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.alert-mini__title {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-mini__meta {
  display: flex;
  gap: 12px;
  font-size: 0.72rem;
  color: var(--text-muted, #9ca3af);
}

/* Decision cards */
.decision-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.decision-card {
  padding: 16px;
  border-radius: var(--radius-md, 8px);
  background: var(--bg-page, #f8f9fa);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
}

.decision-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.decision-card__id {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted, #9ca3af);
}

.decision-card__text {
  font-size: 0.88rem;
  color: var(--text-secondary, #6b7280);
  line-height: 1.65;
  margin-bottom: 12px;
}

.decision-card__actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-md, 8px);
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s var(--ease, ease);
}

.action-btn--approve {
  background: #0a0a0a;
  color: #fff;
}

.action-btn--approve:hover {
  background: #1a1a1a;
}

.action-btn--reject {
  background: transparent;
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.action-btn--reject:hover {
  background: rgba(239, 68, 68, 0.06);
}

.decision-card__resolved {
  font-size: 0.78rem;
  color: var(--text-muted, #9ca3af);
  font-style: italic;
}

/* Detail footer */
.detail-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
  padding-top: 8px;
  border-top: 1px solid var(--border, rgba(0,0,0,0.08));
}
</style>
