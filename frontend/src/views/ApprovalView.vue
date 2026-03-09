<template>
  <div class="approval-view">
    <PageBanner title="审批队列" subtitle="对高敏感工具调用执行双重确认，确保自动化能力始终处于可控边界之内，符合防御侧审慎原则。">
      <template #right>
        <span>Human-in-the-Loop</span>
        <span v-if="pendingCount > 0">{{ pendingCount }} Pending</span>
        <span v-else>{{ approvals.length }} Items</span>
      </template>
    </PageBanner>

    <!-- Tab Navigation -->
    <div class="tab-bar">
      <button
        class="tab-btn"
        :class="{ 'tab-btn--active': activeTab === 'pending' }"
        @click="activeTab = 'pending'; fetchApprovals()"
      >
        待审批
        <span class="tab-count tab-count--amber" v-if="pendingCount > 0">{{ pendingCount }}</span>
      </button>
      <button
        class="tab-btn"
        :class="{ 'tab-btn--active': activeTab === 'all' }"
        @click="activeTab = 'all'; fetchApprovals()"
      >
        全部
        <span class="tab-count">{{ allCount }}</span>
      </button>
    </div>

    <!-- Approval Cards -->
    <div class="approval-list" v-loading="loading">
      <TransitionGroup name="card-list" tag="div" class="approval-cards-wrapper">
        <ApprovalCard
          v-for="item in approvals"
          :key="item.id"
          :item="item"
          :argsExpanded="!!expandedArgs[item.id]"
          @approve="handleApprove"
          @reject="handleReject"
          @toggle-args="toggleArgs(item.id)"
        />
      </TransitionGroup>

      <!-- Empty State -->
      <div class="empty-state" v-if="!loading && approvals.length === 0">
        <div class="empty-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <p class="empty-title">暂无{{ activeTab === 'pending' ? '待审批' : '' }}记录</p>
        <p class="empty-desc">{{ activeTab === 'pending' ? '所有审批请求已处理完毕' : '还没有任何审批记录' }}</p>
      </div>
    </div>

    <!-- Rejection Dialog -->
    <RejectDialog
      :visible="rejectDialogVisible"
      :item="currentRejectItem"
      @update:visible="rejectDialogVisible = $event"
      @confirm="onRejectConfirm"
    />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import PageBanner from '../components/layout/PageBanner.vue'
import { useApproval } from '../composables/useApproval.js'
import ApprovalCard from '../components/approval/ApprovalCard.vue'
import RejectDialog from '../components/approval/RejectDialog.vue'

const {
  activeTab,
  approvals,
  loading,
  rejectDialogVisible,
  currentRejectItem,
  expandedArgs,
  allCount,
  pendingCount,
  toggleArgs,
  fetchApprovals,
  handleApprove,
  handleReject,
  confirmReject,
  rejectReason
} = useApproval()

function onRejectConfirm(reason) {
  rejectReason.value = reason
  confirmReject()
}

onMounted(() => {
  fetchApprovals()
})
</script>

<style scoped>
/* Tab Bar */
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 4px;
  margin-bottom: 20px;
  border-radius: var(--radius-lg, 12px);
  background: var(--bg-page, #f8f9fa);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
  width: fit-content;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: var(--radius-md, 8px);
  background: transparent;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  transition: all 0.2s var(--ease, ease);
}

.tab-btn:hover {
  color: var(--text-primary, #0a0a0a);
  background: rgba(255, 255, 255, 0.6);
}

.tab-btn--active {
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #0a0a0a);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: var(--radius-full, 999px);
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary, #6b7280);
  font-size: 0.72rem;
  font-weight: 700;
}

.tab-count--amber {
  background: rgba(245, 158, 11, 0.15);
  color: #d97706;
}

/* Approval Cards */
.approval-list {
  min-height: 200px;
}

.approval-cards-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Card list transitions */
.card-list-enter-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.card-list-leave-active { transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
.card-list-enter-from { opacity: 0; transform: translateY(12px); }
.card-list-leave-to { opacity: 0; transform: translateX(-16px); }

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  text-align: center;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: var(--radius-lg, 12px);
  background: rgba(34, 197, 94, 0.08);
  color: #22c55e;
  margin-bottom: 20px;
}

.empty-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
  margin-bottom: 6px;
}

.empty-desc {
  font-size: 0.88rem;
  color: var(--text-muted, #9ca3af);
}
</style>
