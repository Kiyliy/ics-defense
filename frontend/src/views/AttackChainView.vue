<template>
  <div>
    <div class="page-header">
      <div class="page-header-copy">
        <h2>攻击链分析</h2>
        <p class="page-subtitle">
          将关联告警、证据与处置决策聚合到同一链路中，帮助分析人员在更强上下文里理解威胁演进与响应路径。
        </p>
      </div>
      <div class="page-header-meta">
        <span>Evidence Driven</span>
        <span>{{ chains.length }} Chains</span>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="chains-grid">
      <div v-for="i in 4" :key="i" class="chain-card chain-card--skeleton">
        <div class="skeleton-line skeleton-title"></div>
        <div class="skeleton-line skeleton-bar"></div>
        <div class="skeleton-line skeleton-short"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="chains.length === 0" class="empty-state">
      <svg class="empty-icon" viewBox="0 0 48 48" fill="none">
        <rect x="4" y="8" width="40" height="32" rx="4" stroke="#94a3b8" stroke-width="2" fill="none"/>
        <path d="M4 16h40M16 16v24" stroke="#94a3b8" stroke-width="2"/>
        <circle cx="30" cy="28" r="4" stroke="#94a3b8" stroke-width="2" fill="none"/>
      </svg>
      <p class="empty-title">暂无攻击链数据</p>
      <p class="empty-sub">当系统检测到关联告警时，攻击链将自动生成</p>
    </div>

    <!-- Chain cards grid -->
    <div v-else class="chains-grid">
      <div
        v-for="chain in chains"
        :key="chain.id"
        :class="['chain-card', { 'chain-card--expanded': expandedId === chain.id }]"
      >
        <!-- Card header area -->
        <div class="chain-card__header" @click="toggleExpand(chain.id)">
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
            <span class="meta-chip meta-chip--status">
              {{ chain.status || 'pending' }}
            </span>
          </div>

          <!-- Expand indicator -->
          <div class="chain-card__expand-hint">
            <svg :class="['expand-chevron', { 'expand-chevron--open': expandedId === chain.id }]" viewBox="0 0 16 16" width="16" height="16">
              <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </div>
        </div>

        <!-- Expanded detail panel -->
        <transition name="expand">
          <div v-if="expandedId === chain.id" class="chain-card__detail">

            <!-- Timeline / Attack stages -->
            <div class="detail-section" v-if="chain.stages && chain.stages.length">
              <h4 class="detail-section__title">
                <svg viewBox="0 0 16 16" width="16" height="16"><circle cx="3" cy="8" r="2" fill="currentColor"/><circle cx="8" cy="8" r="2" fill="currentColor"/><circle cx="13" cy="8" r="2" fill="currentColor"/><line x1="5" y1="8" x2="6" y2="8" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="8" x2="11" y2="8" stroke="currentColor" stroke-width="1.5"/></svg>
                攻击阶段
              </h4>
              <div class="timeline">
                <div v-for="(stg, i) in chain.stages" :key="i" class="timeline__step">
                  <div class="timeline__dot"></div>
                  <div class="timeline__content">
                    <span class="timeline__label">{{ stg.name || stg }}</span>
                    <span class="timeline__time" v-if="stg.time">{{ stg.time }}</span>
                  </div>
                </div>
              </div>
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
                  <el-tag :type="getSeverityTagType(alert.severity)" size="small">
                    {{ alert.severity }}
                  </el-tag>
                </div>
              </div>
            </div>

            <!-- Evidence -->
            <div class="detail-section" v-if="chain.evidence">
              <h4 class="detail-section__title">
                <svg viewBox="0 0 16 16" width="16" height="16"><path d="M10 1H3a1 1 0 00-1 1v12a1 1 0 001 1h10a1 1 0 001-1V5l-4-4z" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M10 1v4h4" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
                证据 Evidence
              </h4>
              <div class="evidence-block">
                <template v-if="typeof chain.evidence === 'object' && chain.evidence !== null">
                  <div v-for="(val, key) in chain.evidence" :key="key" class="evidence-field">
                    <span class="evidence-field__key">{{ key }}</span>
                    <span class="evidence-field__val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
                  </div>
                </template>
                <p v-else class="evidence-text">{{ chain.evidence }}</p>
              </div>
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
                    <button class="action-btn action-btn--approve" @click="handleDecision(dec.id, 'accepted')">
                      <svg viewBox="0 0 16 16" width="14" height="14"><path d="M13 4L6 12 3 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                      批准
                    </button>
                    <button class="action-btn action-btn--reject" @click="handleDecision(dec.id, 'rejected')">
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
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAttackChains, updateDecision } from '../api'
import { normalizeAttackChain } from '../api/view-models.js'
import { getSeverityTagType, getRiskTagType, getStatusTagType } from '../utils/ui.js'

const chains = ref([])
const loading = ref(false)
const expandedId = ref(null)

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function normalizeRisk(level) {
  return String(level || 'unknown').toLowerCase()
}

async function fetchChains() {
  loading.value = true
  try {
    const res = await getAttackChains()
    chains.value = (res.chains || []).map(normalizeAttackChain)
  } catch (err) {
    console.error('Failed to fetch chains:', err)
  } finally {
    loading.value = false
  }
}

async function handleDecision(decisionId, status) {
  try {
    await updateDecision(decisionId, status)
    ElMessage.success('决策已更新')
    await fetchChains()
  } catch (err) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchChains()
})
</script>

<style scoped>
/* ===== Grid layout ===== */
.chains-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

@media (max-width: 900px) {
  .chains-grid {
    grid-template-columns: 1fr;
  }
}

/* ===== Empty state ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
}

.empty-icon {
  width: 64px;
  height: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}

.empty-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}

.empty-sub {
  font-size: 0.88rem;
  color: #94a3b8;
}

/* ===== Skeleton loading ===== */
.chain-card--skeleton {
  padding: 28px 24px;
}

.skeleton-line {
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(148,163,184,0.12) 25%, rgba(148,163,184,0.22) 50%, rgba(148,163,184,0.12) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.6s ease infinite;
}

.skeleton-title {
  width: 60%;
  height: 20px;
  margin-bottom: 16px;
}

.skeleton-bar {
  width: 100%;
  height: 8px;
  margin-bottom: 16px;
}

.skeleton-short {
  width: 40%;
  height: 14px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ===== Chain card ===== */
.chain-card {
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--app-radius-lg, 24px);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--app-shadow-soft, 0 10px 30px rgba(15,23,42,0.1));
  backdrop-filter: blur(16px);
  overflow: hidden;
  transition: box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.chain-card:hover {
  box-shadow: 0 16px 48px rgba(15, 23, 42, 0.14);
  border-color: rgba(79, 140, 255, 0.24);
}

.chain-card--expanded {
  grid-column: 1 / -1;
  border-color: rgba(79, 140, 255, 0.3);
  box-shadow: 0 20px 60px rgba(37, 99, 235, 0.12);
}

/* ===== Card header (clickable) ===== */
.chain-card__header {
  padding: 24px;
  cursor: pointer;
  position: relative;
  transition: background 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.chain-card__header:hover {
  background: rgba(79, 140, 255, 0.03);
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
  color: #94a3b8;
}

.chain-card__name {
  font-size: 1.1rem;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* ===== Risk badge ===== */
.risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.risk-badge__dot {
  width: 8px;
  height: 8px;
}

.risk-badge--critical {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.risk-badge--high {
  background: rgba(249, 115, 22, 0.1);
  color: #ea580c;
}

.risk-badge--medium {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.risk-badge--low {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.risk-badge--unknown,
.risk-badge--info {
  background: rgba(148, 163, 184, 0.1);
  color: #64748b;
}

/* ===== Confidence bar ===== */
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
  color: #94a3b8;
  flex-shrink: 0;
}

.confidence-track {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--app-primary, #4f8cff), var(--app-primary-strong, #2563eb));
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.confidence-value {
  font-size: 0.82rem;
  font-weight: 700;
  color: #0f172a;
  min-width: 36px;
  text-align: right;
}

/* ===== Meta chips ===== */
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
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1;
}

.meta-chip--stage {
  background: rgba(139, 92, 246, 0.1);
  color: #7c3aed;
}

.meta-chip--mitre {
  background: rgba(79, 140, 255, 0.1);
  color: #2563eb;
}

.meta-chip--alerts {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.meta-chip--status {
  background: rgba(148, 163, 184, 0.1);
  color: #475569;
  text-transform: capitalize;
}

/* ===== Expand indicator ===== */
.chain-card__expand-hint {
  display: flex;
  justify-content: center;
  padding-top: 12px;
  color: #94a3b8;
}

.expand-chevron {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.expand-chevron--open {
  transform: rotate(180deg);
}

/* ===== Expand transition ===== */
.expand-enter-active {
  animation: expandIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.expand-leave-active {
  animation: expandIn 0.25s cubic-bezier(0.4, 0, 0.2, 1) reverse;
}

@keyframes expandIn {
  from {
    opacity: 0;
    max-height: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    max-height: 2000px;
    transform: translateY(0);
  }
}

/* ===== Detail panel ===== */
.chain-card__detail {
  padding: 0 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
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
  color: #0f172a;
}

.detail-section__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(79, 140, 255, 0.1);
  color: #2563eb;
  font-size: 0.7rem;
  font-weight: 700;
}

/* ===== Timeline ===== */
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
  background: linear-gradient(90deg, var(--app-primary, #4f8cff), rgba(79, 140, 255, 0.3));
}

.timeline__dot {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--app-primary, #4f8cff), var(--app-primary-strong, #2563eb));
  box-shadow: 0 0 0 4px rgba(79, 140, 255, 0.15);
  position: relative;
  z-index: 1;
}

.timeline__content {
  text-align: center;
}

.timeline__label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #475569;
  display: block;
}

.timeline__time {
  font-size: 0.7rem;
  color: #94a3b8;
}

/* ===== Alert mini cards ===== */
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
  border-radius: var(--app-radius-sm, 12px);
  background: rgba(241, 245, 249, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.1);
  transition: background 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.alert-mini:hover {
  background: rgba(241, 245, 249, 1);
}

.severity-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  flex-shrink: 0;
}

.severity-dot--critical { background: #ef4444; box-shadow: 0 0 8px rgba(239,68,68,0.4); }
.severity-dot--high,
.severity-dot--error { background: #f97316; box-shadow: 0 0 8px rgba(249,115,22,0.3); }
.severity-dot--medium,
.severity-dot--warning { background: #f59e0b; }
.severity-dot--low,
.severity-dot--info { background: #22c55e; }

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
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-mini__meta {
  display: flex;
  gap: 12px;
  font-size: 0.72rem;
  color: #94a3b8;
}

/* ===== Evidence block ===== */
.evidence-block {
  padding: 16px;
  border-radius: var(--app-radius-sm, 12px);
  background: rgba(241, 245, 249, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.evidence-field {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  font-size: 0.84rem;
}

.evidence-field:last-child {
  border-bottom: none;
}

.evidence-field__key {
  font-weight: 700;
  color: #475569;
  min-width: 120px;
  flex-shrink: 0;
  text-transform: capitalize;
}

.evidence-field__val {
  color: #0f172a;
  word-break: break-word;
}

.evidence-text {
  font-size: 0.88rem;
  color: #475569;
  line-height: 1.7;
  white-space: pre-wrap;
}

/* ===== Decision cards ===== */
.decision-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.decision-card {
  padding: 16px;
  border-radius: var(--app-radius-sm, 12px);
  background: rgba(241, 245, 249, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.1);
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
  color: #94a3b8;
}

.decision-card__text {
  font-size: 0.88rem;
  color: #475569;
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
  border-radius: 12px;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.action-btn--approve {
  background: linear-gradient(135deg, #4ade80, #16a34a);
  color: #fff;
  box-shadow: 0 6px 16px rgba(22, 163, 74, 0.2);
}

.action-btn--approve:hover {
  box-shadow: 0 8px 24px rgba(22, 163, 74, 0.3);
  transform: translateY(-1px);
}

.action-btn--reject {
  background: linear-gradient(135deg, #fb7185, #e11d48);
  color: #fff;
  box-shadow: 0 6px 16px rgba(225, 29, 72, 0.2);
}

.action-btn--reject:hover {
  box-shadow: 0 8px 24px rgba(225, 29, 72, 0.3);
  transform: translateY(-1px);
}

.decision-card__resolved {
  font-size: 0.78rem;
  color: #94a3b8;
  font-style: italic;
}

/* ===== Detail footer ===== */
.detail-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: #94a3b8;
  padding-top: 8px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
}
</style>
