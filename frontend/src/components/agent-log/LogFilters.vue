<template>
  <div class="filter-panel">
    <div class="filter-fields">
      <div class="filter-group">
        <label class="filter-label">Trace ID</label>
        <el-input
          v-model="filters.trace_id"
          placeholder="输入 trace_id 精确筛选..."
          clearable
          style="width: 280px"
        />
      </div>

      <div class="filter-group">
        <label class="filter-label">时间范围</label>
        <el-select v-model="filters.days" style="width: 160px">
          <el-option :value="1" label="最近 1 天" />
          <el-option :value="7" label="最近 7 天" />
          <el-option :value="30" label="最近 30 天" />
        </el-select>
      </div>

      <div class="filter-actions">
        <el-button type="primary" @click="$emit('search')">
          <el-icon><Search /></el-icon> 查询
        </el-button>
        <el-button @click="$emit('reset')">重置</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'

defineProps({
  filters: { type: Object, required: true },
})

defineEmits(['search', 'reset'])
</script>

<style scoped>
.filter-panel {
  margin-bottom: 16px;
  padding: 20px 24px;
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--border, rgba(0, 0, 0, 0.08));
  background: var(--bg-primary, #fff);
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
  color: var(--text-muted, #9ca3af);
}

.filter-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

@media (max-width: 768px) {
  .filter-fields {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-actions {
    margin-left: 0;
  }
  .filter-group :deep(.el-input),
  .filter-group :deep(.el-select) {
    width: 100% !important;
  }
}
</style>
