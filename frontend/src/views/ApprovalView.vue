<template>
  <div class="approval-view">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-copy">
        <h2>审批队列</h2>
        <p class="page-subtitle">
          对高敏感工具调用执行双重确认，确保自动化能力始终处于可控边界之内，符合防御侧审慎原则。
        </p>
      </div>
      <div class="page-header-meta">
        <span>Human-in-the-Loop</span>
        <span class="pending-badge" v-if="pendingCount > 0">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          {{ pendingCount }} Pending
        </span>
        <span v-else>{{ approvals.length }} Items</span>
      </div>
    </div>

    <!-- Pending Count Hero (only when pending) -->
    <div class="pending-hero" v-if="activeTab === 'pending' && pendingCount > 0">
      <div class="pending-hero-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      </div>
      <div class="pending-hero-info">
        <span class="pending-hero-value">{{ pendingCount }}</span>
        <span class="pending-hero-label">项待审批</span>
      </div>
      <p class="pending-hero-desc">以下工具调用正等待您的审批确认，请及时处理以避免阻塞自动化流程。</p>
    </div>

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
        <div
          v-for="item in approvals"
          :key="item.id"
          class="approval-card"
          :class="'approval-card--' + item.status"
        >
          <!-- Left Status Bar -->
          <div class="card-status-bar" :class="'card-status-bar--' + item.status"></div>

          <div class="card-body">
            <!-- Card Header -->
            <div class="card-header">
              <div class="card-header-left">
                <h4 class="card-tool-name">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                  {{ item.tool_name }}
                </h4>
                <span class="card-trace-id">{{ item.trace_id }}</span>
              </div>
              <span class="card-status-badge" :class="'card-status-badge--' + item.status">
                {{ statusLabel(item.status) }}
              </span>
            </div>

            <!-- Args Preview -->
            <div class="card-args-section">
              <button
                class="card-args-toggle"
                @click="toggleArgs(item.id)"
                :class="{ 'card-args-toggle--open': expandedArgs[item.id] }"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                <span class="card-args-preview" v-if="!expandedArgs[item.id]">{{ truncateArgs(item.tool_args) }}</span>
                <span v-else>收起参数</span>
              </button>
              <Transition name="args-expand">
                <pre
                  class="card-args-code"
                  v-if="expandedArgs[item.id]"
                >{{ formatArgs(item.tool_args) }}</pre>
              </Transition>
            </div>

            <!-- Card Footer -->
            <div class="card-footer">
              <span class="card-time">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                {{ item.created_at }}
              </span>

              <div class="card-actions" v-if="item.status === 'pending'">
                <button class="card-action-btn card-action-btn--approve" @click="handleApprove(item)">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  批准
                </button>
                <button class="card-action-btn card-action-btn--reject" @click="handleReject(item)">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  拒绝
                </button>
              </div>
              <span class="card-processed" v-else>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                已处理
              </span>
            </div>
          </div>
        </div>
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
    <el-dialog v-model="rejectDialogVisible" title="拒绝确认" width="480px" class="reject-dialog" :append-to-body="true">
      <div class="reject-dialog-content">
        <div class="reject-warning-banner">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <div>
            <strong>确认拒绝此工具调用</strong>
            <p v-if="currentRejectItem">工具「{{ currentRejectItem.tool_name }}」的执行请求将被拒绝。</p>
          </div>
        </div>

        <div class="reject-form-group">
          <label class="reject-form-label">拒绝原因</label>
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="3"
            placeholder="请输入拒绝原因，以便后续审计追溯..."
          />
        </div>
      </div>
      <template #footer>
        <div class="reject-dialog-footer">
          <el-button @click="rejectDialogVisible = false">取消</el-button>
          <el-button type="danger" :disabled="!rejectReason.trim()" @click="confirmReject">
            确认拒绝
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApprovals, respondApproval } from '../api'

const activeTab = ref('pending')
const approvals = ref([])
const loading = ref(false)
const rejectDialogVisible = ref(false)
const rejectReason = ref('')
const currentRejectItem = ref(null)
const expandedArgs = ref({})
const allCount = ref(0)

const pendingCount = computed(() => {
  if (activeTab.value === 'pending') return approvals.value.length
  return approvals.value.filter(a => a.status === 'pending').length
})

function toggleArgs(id) {
  expandedArgs.value[id] = !expandedArgs.value[id]
}

function statusLabel(status) {
  const map = { pending: '待审批', approved: '已批准', rejected: '已拒绝' }
  return map[status] || status
}

function truncateArgs(args) {
  const str = typeof args === 'string' ? args : JSON.stringify(args)
  return str.length > 60 ? str.slice(0, 60) + '...' : str
}

function formatArgs(args) {
  try {
    const obj = typeof args === 'string' ? JSON.parse(args) : args
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(args)
  }
}

async function fetchApprovals() {
  loading.value = true
  try {
    const params = activeTab.value === 'pending' ? { status: 'pending' } : {}
    const res = await getApprovals(params)
    approvals.value = res.approvals || []
    // Also fetch total count for "all" tab badge
    if (activeTab.value === 'pending') {
      try {
        const allRes = await getApprovals({})
        allCount.value = (allRes.approvals || []).length
      } catch { allCount.value = 0 }
    } else {
      allCount.value = approvals.value.length
    }
  } catch (err) {
    console.error('Failed to fetch approvals:', err)
  } finally {
    loading.value = false
  }
}

async function handleApprove(item) {
  try {
    await ElMessageBox.confirm(`确认批准工具「${item.tool_name}」的执行请求？`, '确认批准', {
      confirmButtonText: '批准',
      cancelButtonText: '取消',
      type: 'info',
    })
    await respondApproval(item.id, 'approved')
    ElMessage.success('已批准')
    fetchApprovals()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

function handleReject(item) {
  currentRejectItem.value = item
  rejectReason.value = ''
  rejectDialogVisible.value = true
}

async function confirmReject() {
  try {
    await respondApproval(currentRejectItem.value.id, 'rejected', rejectReason.value)
    ElMessage.success('已拒绝')
    rejectDialogVisible.value = false
    fetchApprovals()
  } catch (err) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchApprovals()
})
</script>

<style scoped>
/* ── Pending Hero ── */
.pending-hero {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  margin-bottom: 20px;
  border-radius: var(--app-radius-md);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(251, 191, 36, 0.06));
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.pending-hero-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  color: #fff;
  box-shadow: 0 8px 20px rgba(245, 158, 11, 0.25);
  flex-shrink: 0;
}

.pending-hero-info {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.pending-hero-value {
  font-size: 2rem;
  font-weight: 800;
  color: #d97706;
  letter-spacing: -0.04em;
}

.pending-hero-label {
  font-size: 0.95rem;
  font-weight: 600;
  color: #92400e;
}

.pending-hero-desc {
  margin-left: auto;
  font-size: 0.84rem;
  color: #92400e;
  max-width: 320px;
  text-align: right;
  line-height: 1.5;
}

.pending-badge {
  background: rgba(245, 158, 11, 0.15) !important;
  color: #f59e0b !important;
  border-color: rgba(245, 158, 11, 0.3) !important;
}

/* ── Tab Bar ── */
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 4px;
  margin-bottom: 20px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.12);
  width: fit-content;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  background: transparent;
  font-size: 0.88rem;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.tab-btn:hover {
  color: #0f172a;
  background: rgba(255, 255, 255, 0.6);
}

.tab-btn--active {
  background: #fff;
  color: #0f172a;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(148, 163, 184, 0.1);
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: #64748b;
  font-size: 0.72rem;
  font-weight: 700;
}

.tab-count--amber {
  background: rgba(245, 158, 11, 0.15);
  color: #d97706;
}

/* ── Approval Cards ── */
.approval-list {
  min-height: 200px;
}

.approval-cards-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.approval-card {
  display: flex;
  border-radius: var(--app-radius-md);
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(255, 255, 255, 0.7);
  box-shadow: var(--app-shadow-soft);
  backdrop-filter: blur(16px);
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.approval-card:hover {
  box-shadow: 0 12px 36px rgba(15, 23, 42, 0.12);
  transform: translateY(-1px);
}

/* Status Bar (left edge) */
.card-status-bar {
  width: 4px;
  flex-shrink: 0;
}

.card-status-bar--pending {
  background: linear-gradient(180deg, #fbbf24, #f59e0b);
}

.card-status-bar--approved {
  background: linear-gradient(180deg, #4ade80, #16a34a);
}

.card-status-bar--rejected {
  background: linear-gradient(180deg, #fb7185, #e11d48);
}

.card-body {
  flex: 1;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Card Header */
.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.card-header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.card-tool-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.05rem;
  font-weight: 700;
  color: #0f172a;
}

.card-tool-name svg {
  color: var(--app-primary);
  flex-shrink: 0;
}

.card-trace-id {
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 0.78rem;
  color: #94a3b8;
  word-break: break-all;
}

.card-status-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 600;
  flex-shrink: 0;
}

.card-status-badge--pending {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.card-status-badge--approved {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.card-status-badge--rejected {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

/* Args Section */
.card-args-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-args-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  border-radius: 8px;
  background: rgba(79, 140, 255, 0.06);
  color: #475569;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: left;
  width: fit-content;
  max-width: 100%;
}

.card-args-toggle svg {
  color: var(--app-primary);
  flex-shrink: 0;
}

.card-args-toggle:hover {
  background: rgba(79, 140, 255, 0.12);
  color: #1d4ed8;
}

.card-args-toggle--open {
  background: rgba(79, 140, 255, 0.1);
  color: #2563eb;
}

.card-args-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 0.78rem;
}

.card-args-code {
  padding: 14px 18px;
  border-radius: 12px;
  background: #061120;
  color: #93c5fd;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 0.78rem;
  line-height: 1.7;
  overflow: auto;
  max-height: 240px;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

/* Args expand transition */
.args-expand-enter-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.args-expand-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.args-expand-enter-from {
  opacity: 0;
  max-height: 0;
  transform: translateY(-8px);
}

.args-expand-leave-to {
  opacity: 0;
  max-height: 0;
}

/* Card Footer */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}

.card-time {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.8rem;
  color: #94a3b8;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.card-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 10px;
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.card-action-btn--approve {
  background: linear-gradient(135deg, #4ade80, #16a34a);
  color: #fff;
  box-shadow: 0 4px 14px rgba(34, 197, 94, 0.25);
}

.card-action-btn--approve:hover {
  box-shadow: 0 6px 20px rgba(34, 197, 94, 0.35);
  transform: translateY(-1px);
}

.card-action-btn--reject {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.card-action-btn--reject:hover {
  background: rgba(239, 68, 68, 0.18);
}

.card-processed {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.8rem;
  color: #94a3b8;
}

/* Card list transitions */
.card-list-enter-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.card-list-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.card-list-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.card-list-leave-to {
  opacity: 0;
  transform: translateX(-16px);
}

/* ── Empty State ── */
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
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(34, 197, 94, 0.04));
  color: #22c55e;
  margin-bottom: 20px;
}

.empty-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 6px;
}

.empty-desc {
  font-size: 0.88rem;
  color: #94a3b8;
}

/* ── Reject Dialog ── */
.reject-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.reject-warning-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.reject-warning-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.reject-warning-banner strong {
  display: block;
  font-size: 0.92rem;
  color: #b91c1c;
  margin-bottom: 4px;
}

.reject-warning-banner p {
  font-size: 0.84rem;
  color: #991b1b;
  line-height: 1.5;
  margin: 0;
}

.reject-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.reject-form-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #64748b;
}

.reject-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .pending-hero {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .pending-hero-desc {
    margin-left: 0;
    text-align: left;
    max-width: none;
  }

  .card-header {
    flex-direction: column;
  }

  .card-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .card-actions {
    width: 100%;
  }

  .card-action-btn {
    flex: 1;
    justify-content: center;
  }
}
</style>
