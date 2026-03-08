<template>
  <div>
    <div class="page-header">
      <div class="page-header-copy">
        <h1>攻击链分析</h1>
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
      <div v-for="i in 4" :key="i" class="chain-skeleton">
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
      <ChainCard
        v-for="chain in chains"
        :key="chain.id"
        :chain="chain"
        :expanded="expandedId === chain.id"
        @toggle="toggleExpand(chain.id)"
        @decide="handleDecision"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useChains } from '../composables/useChains.js'
import ChainCard from '../components/chains/ChainCard.vue'

const { chains, loading, expandedId, toggleExpand, fetchChains, handleDecision } = useChains()

onMounted(() => {
  fetchChains()
})
</script>

<style scoped>
.chains-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

@media (max-width: 900px) {
  .chains-grid { grid-template-columns: 1fr; }
}

/* Skeleton */
.chain-skeleton {
  padding: 28px 24px;
  border: 1px solid var(--border, rgba(0,0,0,0.08));
  border-radius: var(--radius-lg, 12px);
  background: var(--bg-primary, #fff);
}

.skeleton-line {
  border-radius: var(--radius-md, 8px);
  background: linear-gradient(90deg, rgba(148,163,184,0.12) 25%, rgba(148,163,184,0.22) 50%, rgba(148,163,184,0.12) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.6s ease infinite;
}

.skeleton-title { width: 60%; height: 20px; margin-bottom: 16px; }
.skeleton-bar { width: 100%; height: 8px; margin-bottom: 16px; }
.skeleton-short { width: 40%; height: 14px; }

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
}

.empty-icon { width: 64px; height: 64px; margin-bottom: 20px; opacity: 0.5; }
.empty-title { font-size: 1.1rem; font-weight: 700; color: var(--text-primary, #0a0a0a); margin-bottom: 8px; }
.empty-sub { font-size: 0.88rem; color: var(--text-muted, #9ca3af); }
</style>
