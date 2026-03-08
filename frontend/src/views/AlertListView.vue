<template>
  <div class="alert-view">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-copy">
        <h2>告警列表</h2>
        <p class="page-subtitle">
          统一查看全域告警、按风险与来源快速过滤，并将关键事件直接送入 AI 研判与攻击链分析流程。
        </p>
      </div>
      <div class="page-header-meta">
        <span>Alert Triage</span>
        <span>{{ store.total || 0 }} Total Records</span>
      </div>
    </div>

    <!-- Filter Card -->
    <div class="filter-panel">
      <div class="filter-fields">
        <div class="filter-group">
          <label class="filter-label">等级</label>
          <el-select v-model="store.filters.severity" placeholder="全部" clearable style="width: 160px">
            <el-option label="Critical" value="critical" />
            <el-option label="High" value="high" />
            <el-option label="Medium" value="medium" />
            <el-option label="Low" value="low" />
          </el-select>
        </div>

        <div class="filter-group">
          <label class="filter-label">来源</label>
          <el-select v-model="store.filters.source" placeholder="全部" clearable style="width: 160px">
            <el-option label="WAF" value="waf" />
            <el-option label="NIDS" value="nids" />
            <el-option label="HIDS" value="hids" />
            <el-option label="SOC" value="soc" />
          </el-select>
        </div>

        <div class="filter-group">
          <label class="filter-label">状态</label>
          <el-select v-model="store.filters.status" placeholder="全部" clearable style="width: 160px">
            <el-option label="Open" value="open" />
            <el-option label="Analyzing" value="analyzing" />
            <el-option label="Analyzed" value="analyzed" />
            <el-option label="Resolved" value="resolved" />
          </el-select>
        </div>

        <div class="filter-actions">
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>
      </div>
    </div>

    <!-- Summary Strip -->
    <div class="summary-strip">
      <div class="summary-chip">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        共 <strong>{{ store.total || 0 }}</strong> 条告警
      </div>
      <div class="summary-divider"></div>
      <div class="summary-chip summary-chip--selected" v-if="store.selectedIds.length > 0">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
        已选 <strong>{{ store.selectedIds.length }}</strong> 条
      </div>
    </div>

    <!-- Table Card -->
    <div class="table-card">
      <el-table
        :data="store.alerts"
        v-loading="store.loading"
        class="alert-table"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="id" label="ID" width="72">
          <template #default="{ row }">
            <span class="cell-id">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="等级" width="120">
          <template #default="{ row }">
            <div class="severity-cell">
              <span class="severity-dot" :class="'severity-dot--' + row.severity"></span>
              <span class="severity-text" :class="'severity-text--' + row.severity">{{ row.severity }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="110">
          <template #default="{ row }">
            <span class="source-chip">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
              {{ row.source?.toUpperCase() }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="告警标题" min-width="260">
          <template #default="{ row }">
            <span class="cell-title" :title="row.title">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="src_ip" label="源IP" width="140">
          <template #default="{ row }">
            <span class="cell-ip">{{ row.src_ip || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="dst_ip" label="目标IP" width="140">
          <template #default="{ row }">
            <span class="cell-ip">{{ row.dst_ip || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <span class="status-pill" :class="'status-pill--' + row.status">
              {{ row.status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">
            <span class="cell-time">{{ row.created_at }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="72" fixed="right" align="center">
          <template #default="{ row }">
            <el-tooltip content="查看详情" placement="top" :show-after="300">
              <button class="action-icon-btn" @click="showDetail(row)">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              </button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-pagination">
        <el-pagination
          v-model:current-page="store.filters.page"
          v-model:page-size="store.filters.limit"
          :page-sizes="[10, 20, 50]"
          :total="store.total"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </div>

    <!-- Floating Selection Toolbar -->
    <Transition name="float-bar">
      <div class="floating-toolbar" v-if="store.selectedIds.length > 0">
        <div class="floating-toolbar-inner">
          <div class="floating-count">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            已选择 <strong>{{ store.selectedIds.length }}</strong> 条告警
          </div>
          <el-button
            type="warning"
            @click="handleAnalyze"
            class="analyze-btn"
          >
            <el-icon><MagicStick /></el-icon>
            AI 分析 ({{ store.selectedIds.length }})
          </el-button>
        </div>
      </div>
    </Transition>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="告警详情" width="720px" class="alert-detail-dialog" :append-to-body="true">
      <div class="detail-content" v-if="currentDetail">
        <!-- Section: 基本信息 -->
        <div class="detail-section">
          <h4 class="detail-section-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            基本信息
          </h4>
          <div class="detail-grid">
            <div class="detail-field">
              <span class="detail-field-label">ID</span>
              <span class="detail-field-value">#{{ currentDetail.id }}</span>
            </div>
            <div class="detail-field">
              <span class="detail-field-label">来源</span>
              <span class="source-chip">{{ currentDetail.source?.toUpperCase() }}</span>
            </div>
            <div class="detail-field">
              <span class="detail-field-label">等级</span>
              <div class="severity-cell">
                <span class="severity-dot" :class="'severity-dot--' + currentDetail.severity"></span>
                <span class="severity-text" :class="'severity-text--' + currentDetail.severity">{{ currentDetail.severity }}</span>
              </div>
            </div>
            <div class="detail-field">
              <span class="detail-field-label">状态</span>
              <span class="status-pill" :class="'status-pill--' + currentDetail.status">{{ currentDetail.status }}</span>
            </div>
            <div class="detail-field detail-field--full">
              <span class="detail-field-label">标题</span>
              <span class="detail-field-value detail-field-value--title">{{ currentDetail.title }}</span>
            </div>
            <div class="detail-field detail-field--full">
              <span class="detail-field-label">时间</span>
              <span class="detail-field-value detail-field-value--muted">{{ currentDetail.created_at }}</span>
            </div>
          </div>
        </div>

        <!-- Section: 网络信息 -->
        <div class="detail-section">
          <h4 class="detail-section-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M7 2v20"/><path d="M17 2v20"/><path d="M2 12h20"/><path d="M2 7h5"/><path d="M2 17h5"/><path d="M17 7h5"/><path d="M17 17h5"/></svg>
            网络信息
          </h4>
          <div class="detail-grid">
            <div class="detail-field">
              <span class="detail-field-label">源 IP</span>
              <span class="detail-field-value cell-ip">{{ currentDetail.src_ip || '-' }}</span>
            </div>
            <div class="detail-field">
              <span class="detail-field-label">目标 IP</span>
              <span class="detail-field-value cell-ip">{{ currentDetail.dst_ip || '-' }}</span>
            </div>
          </div>
        </div>

        <!-- Section: 原始数据 -->
        <div class="detail-section">
          <h4 class="detail-section-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            原始数据
          </h4>
          <pre class="detail-code-block">{{ JSON.stringify(currentDetail.raw_data || currentDetail, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAlertStore } from '../stores/alert'
import { getSeverityTagType, getStatusTagType } from '../utils/ui.js'

const store = useAlertStore()
const router = useRouter()
const detailVisible = ref(false)
const currentDetail = ref(null)

function handleSearch() {
  store.fetchAlerts()
}

function handleReset() {
  store.setFilters({ severity: '', source: '', status: '', page: 1 })
  store.fetchAlerts()
}

function handleSelectionChange(rows) {
  store.toggleSelection(rows.map((r) => r.id))
}

async function handleAnalyze() {
  const res = await store.submitAnalysis()
  if (res) {
    store.toggleSelection([])
    await store.fetchAlerts()
    if (res.trace_id) {
      ElMessage.success(`分析已提交，Trace ID: ${res.trace_id}`)
      store.pollAnalysisResult(res.trace_id).then((result) => {
        if (result) {
          const riskLevel = result.risk_level || result.risk || '未知'
          ElMessage.success(`分析完成，风险等级: ${riskLevel}`)
          store.fetchAlerts()
        }
      })
      await router.push({ path: '/chains' })
    } else if (res.attack_chain_id) {
      ElMessage.success(`分析完成，攻击链 ID: ${res.attack_chain_id}`)
      await router.push('/chains')
    } else {
      ElMessage.success('分析请求已完成')
    }
  } else {
    ElMessage.error('分析提交失败')
  }
}

async function showDetail(row) {
  detailVisible.value = true
  currentDetail.value = row

  const detail = await store.fetchAlertDetail(row.id)
  if (detail) {
    currentDetail.value = detail
  } else {
    ElMessage.warning('告警详情加载失败，当前仅显示列表摘要信息')
  }
}

onMounted(() => {
  store.fetchAlerts()
})
</script>

<style scoped>
/* ── Filter Panel ── */
.filter-panel {
  margin-bottom: 16px;
  padding: 20px 24px;
  border-radius: var(--app-radius-md);
  border: 1px solid rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px);
  box-shadow: var(--app-shadow-soft);
}

.filter-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 20px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--app-text-muted);
}

.filter-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

/* ── Summary Strip ── */
.summary-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 0 4px;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.84rem;
  color: #475569;
}

.summary-chip strong {
  color: #0f172a;
  font-weight: 700;
  font-size: 0.92rem;
}

.summary-chip--selected {
  color: var(--app-primary-strong);
}

.summary-chip--selected strong {
  color: var(--app-primary-strong);
}

.summary-divider {
  width: 1px;
  height: 16px;
  background: rgba(148, 163, 184, 0.3);
}

/* ── Table Card ── */
.table-card {
  border-radius: var(--app-radius-md);
  border: 1px solid rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(16px);
  box-shadow: var(--app-shadow-soft);
  padding: 24px;
  overflow: hidden;
}

.alert-table {
  --el-table-border-color: rgba(148, 163, 184, 0.12);
  --el-table-header-bg-color: rgba(15, 23, 42, 0.03);
  --el-table-row-hover-bg-color: rgba(79, 140, 255, 0.06);
  border-radius: 16px;
  overflow: hidden;
}

/* Cell: ID */
.cell-id {
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 0.82rem;
  color: var(--app-text-muted);
  font-weight: 500;
}

/* Cell: Severity */
.severity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.severity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.severity-dot--critical {
  background: #ef4444;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
}

.severity-dot--high {
  background: #f97316;
  box-shadow: 0 0 8px rgba(249, 115, 22, 0.4);
}

.severity-dot--medium {
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.35);
}

.severity-dot--low {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.35);
}

.severity-text {
  font-size: 0.82rem;
  font-weight: 600;
  text-transform: capitalize;
}

.severity-text--critical { color: #dc2626; }
.severity-text--high { color: #ea580c; }
.severity-text--medium { color: #d97706; }
.severity-text--low { color: #16a34a; }

/* Cell: Source Chip */
.source-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 8px;
  background: rgba(79, 140, 255, 0.08);
  color: #3b82f6;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.03em;
}

/* Cell: Title */
.cell-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: #0f172a;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Cell: IP */
.cell-ip {
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 0.82rem;
  color: #475569;
}

/* Cell: Status Pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 600;
  text-transform: capitalize;
  letter-spacing: 0.02em;
}

.status-pill--open {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.status-pill--analyzing {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.status-pill--analyzed {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.status-pill--resolved {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

/* Cell: Time */
.cell-time {
  font-size: 0.8rem;
  color: #94a3b8;
}

/* Action Icon Button */
.action-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.action-icon-btn:hover {
  background: rgba(79, 140, 255, 0.1);
  color: var(--app-primary-strong);
}

/* Pagination */
.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

/* ── Floating Toolbar ── */
.floating-toolbar {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
}

.floating-toolbar-inner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 12px 12px 20px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(148, 163, 184, 0.15);
  box-shadow: 0 20px 60px rgba(2, 8, 23, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.06) inset;
  color: #e2e8f0;
}

.floating-count {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  white-space: nowrap;
}

.floating-count strong {
  color: #93c5fd;
  font-size: 1rem;
}

.analyze-btn {
  white-space: nowrap;
}

/* Float bar transitions */
.float-bar-enter-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.float-bar-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.float-bar-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(24px);
}

.float-bar-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(16px);
}

/* ── Detail Dialog ── */
.detail-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  font-weight: 700;
  color: #0f172a;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.detail-section-title svg {
  color: var(--app-primary);
  flex-shrink: 0;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}

.detail-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-field--full {
  grid-column: 1 / -1;
}

.detail-field-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #94a3b8;
}

.detail-field-value {
  font-size: 0.88rem;
  font-weight: 500;
  color: #0f172a;
}

.detail-field-value--title {
  font-weight: 600;
  line-height: 1.5;
}

.detail-field-value--muted {
  color: #64748b;
  font-size: 0.84rem;
}

.detail-code-block {
  padding: 16px 20px;
  border-radius: 14px;
  background: #061120;
  color: #93c5fd;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 0.8rem;
  line-height: 1.7;
  overflow: auto;
  max-height: 320px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .filter-fields {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-actions {
    margin-left: 0;
  }

  .summary-strip {
    flex-wrap: wrap;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }

  .floating-toolbar-inner {
    flex-direction: column;
    gap: 12px;
  }
}
</style>
