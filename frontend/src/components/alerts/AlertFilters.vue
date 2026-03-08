<template>
  <div class="filter-panel">
    <div class="filter-fields">
      <div class="filter-group">
        <label class="filter-label">等级</label>
        <el-select v-model="local.severity" placeholder="全部" clearable style="width: 160px">
          <el-option label="Critical" value="critical" />
          <el-option label="High" value="high" />
          <el-option label="Medium" value="medium" />
          <el-option label="Low" value="low" />
        </el-select>
      </div>

      <div class="filter-group">
        <label class="filter-label">来源</label>
        <el-select v-model="local.source" placeholder="全部" clearable style="width: 160px">
          <el-option label="WAF" value="waf" />
          <el-option label="NIDS" value="nids" />
          <el-option label="HIDS" value="hids" />
          <el-option label="SOC" value="soc" />
        </el-select>
      </div>

      <div class="filter-group">
        <label class="filter-label">状态</label>
        <el-select v-model="local.status" placeholder="全部" clearable style="width: 160px">
          <el-option label="Open" value="open" />
          <el-option label="Analyzing" value="analyzing" />
          <el-option label="Analyzed" value="analyzed" />
          <el-option label="Resolved" value="resolved" />
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
import { reactive, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'

const props = defineProps({
  filters: { type: Object, required: true }
})

defineEmits(['search', 'reset'])

const local = reactive({
  severity: props.filters.severity || '',
  source: props.filters.source || '',
  status: props.filters.status || ''
})

watch(() => props.filters, (f) => {
  local.severity = f.severity || ''
  local.source = f.source || ''
  local.status = f.status || ''
}, { deep: true })

watch(local, (v) => {
  props.filters.severity = v.severity
  props.filters.source = v.source
  props.filters.status = v.status
})
</script>

<style scoped>
.filter-panel {
  margin-bottom: 16px;
  padding: 20px 24px;
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
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
}
</style>
