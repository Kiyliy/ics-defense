<template>
  <div class="table-card">
    <!-- Summary Strip -->
    <div class="summary-strip">
      <div class="summary-chip">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        共 <strong>{{ total || 0 }}</strong> 条告警
      </div>
    </div>

    <el-table
      :data="alerts"
      v-loading="loading"
      class="alert-table"
      @selection-change="onSelectionChange"
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
          <span class="source-chip">{{ row.source?.toUpperCase() }}</span>
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
          <span class="status-pill" :class="'status-pill--' + row.status">{{ row.status }}</span>
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
            <button class="action-icon-btn" @click="$emit('show-detail', row)">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            </button>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <div class="table-pagination">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @update:current-page="$emit('update:page', $event)"
        @update:page-size="$emit('update:pageSize', $event)"
        @size-change="$emit('update:pageSize', $event)"
        @current-change="$emit('update:page', $event)"
      />
    </div>
  </div>
</template>

<script setup>
defineProps({
  alerts: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 10 }
})

const emit = defineEmits(['selection-change', 'show-detail', 'update:page', 'update:pageSize'])

function onSelectionChange(rows) {
  emit('selection-change', rows)
}
</script>

<style scoped>
.table-card {
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
  background: var(--bg-primary, #fff);
  padding: 24px;
  overflow: hidden;
}

.summary-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.84rem;
  color: var(--text-secondary, #6b7280);
}

.summary-chip strong {
  color: var(--text-primary, #0a0a0a);
  font-weight: 700;
  font-size: 0.92rem;
}

.alert-table {
  --el-table-border-color: var(--border, rgba(0,0,0,0.08));
  --el-table-header-bg-color: var(--bg-page, #f8f9fa);
  --el-table-row-hover-bg-color: var(--bg-hover, #f3f4f6);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
}

.cell-id {
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
  color: var(--text-muted, #9ca3af);
  font-weight: 500;
}

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

.severity-dot--critical { background: #ef4444; }
.severity-dot--high { background: #f97316; }
.severity-dot--medium { background: #f59e0b; }
.severity-dot--low { background: #22c55e; }

.severity-text {
  font-size: 0.82rem;
  font-weight: 600;
  text-transform: capitalize;
}

.severity-text--critical { color: #dc2626; }
.severity-text--high { color: #ea580c; }
.severity-text--medium { color: #d97706; }
.severity-text--low { color: #16a34a; }

.source-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: var(--radius-md, 8px);
  background: rgba(59, 130, 246, 0.08);
  color: var(--accent, #3b82f6);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.cell-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cell-ip {
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
  color: var(--text-secondary, #6b7280);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--radius-full, 999px);
  font-size: 0.76rem;
  font-weight: 600;
  text-transform: capitalize;
  letter-spacing: 0.02em;
}

.status-pill--open { background: rgba(239, 68, 68, 0.1); color: #dc2626; }
.status-pill--analyzing { background: rgba(245, 158, 11, 0.1); color: #d97706; }
.status-pill--analyzed { background: rgba(59, 130, 246, 0.1); color: #2563eb; }
.status-pill--resolved { background: rgba(34, 197, 94, 0.1); color: #16a34a; }

.cell-time {
  font-size: 0.8rem;
  color: var(--text-muted, #9ca3af);
}

.action-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md, 8px);
  border: none;
  background: transparent;
  color: var(--text-muted, #9ca3af);
  cursor: pointer;
  transition: all 0.2s var(--ease, ease);
}

.action-icon-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  color: var(--accent, #3b82f6);
}

.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
