<template>
  <div>
    <div class="page-header">
      <h2>告警列表</h2>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="hover" style="margin-bottom: 16px">
      <el-form :inline="true" :model="store.filters">
        <el-form-item label="等级">
          <el-select
            v-model="store.filters.severity"
            placeholder="全部"
            clearable
            style="width: 130px"
          >
            <el-option label="Critical" value="critical" />
            <el-option label="High" value="high" />
            <el-option label="Medium" value="medium" />
            <el-option label="Low" value="low" />
          </el-select>
        </el-form-item>

        <el-form-item label="来源">
          <el-select
            v-model="store.filters.source"
            placeholder="全部"
            clearable
            style="width: 130px"
          >
            <el-option label="WAF" value="waf" />
            <el-option label="NIDS" value="nids" />
            <el-option label="HIDS" value="hids" />
            <el-option label="SOC" value="soc" />
          </el-select>
        </el-form-item>

        <el-form-item label="状态">
          <el-select
            v-model="store.filters.status"
            placeholder="全部"
            clearable
            style="width: 130px"
          >
            <el-option label="Open" value="open" />
            <el-option label="Analyzing" value="analyzing" />
            <el-option label="Resolved" value="resolved" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 操作栏 -->
    <div style="margin-bottom: 12px; display: flex; gap: 8px">
      <el-button
        type="warning"
        :disabled="store.selectedIds.length === 0"
        @click="handleAnalyze"
      >
        <el-icon><MagicStick /></el-icon>
        AI 分析 ({{ store.selectedIds.length }})
      </el-button>
    </div>

    <!-- 告警表格 -->
    <el-card shadow="hover">
      <el-table
        :data="store.alerts"
        v-loading="store.loading"
        stripe
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column prop="severity" label="等级" width="100">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="告警标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="src_ip" label="源IP" width="140" />
        <el-table-column prop="dst_ip" label="目标IP" width="140" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="statusType(row.status)"
              size="small"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="showDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
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
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="告警详情" width="600px">
      <el-descriptions :column="2" border v-if="currentDetail">
        <el-descriptions-item label="ID">{{ currentDetail.id }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ currentDetail.source }}</el-descriptions-item>
        <el-descriptions-item label="等级">
          <el-tag :type="severityType(currentDetail.severity)" size="small">
            {{ currentDetail.severity }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">{{ currentDetail.status }}</el-descriptions-item>
        <el-descriptions-item label="标题" :span="2">{{ currentDetail.title }}</el-descriptions-item>
        <el-descriptions-item label="源IP">{{ currentDetail.src_ip }}</el-descriptions-item>
        <el-descriptions-item label="目标IP">{{ currentDetail.dst_ip }}</el-descriptions-item>
        <el-descriptions-item label="时间" :span="2">{{ currentDetail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="原始数据" :span="2">
          <pre style="white-space: pre-wrap; font-size: 12px; max-height: 200px; overflow: auto">{{ JSON.stringify(currentDetail.raw_data || currentDetail, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAlertStore } from '../stores/alert'

const store = useAlertStore()
const detailVisible = ref(false)
const currentDetail = ref(null)

function severityType(severity) {
  const map = { critical: 'danger', high: 'warning', medium: '', low: 'info' }
  return map[severity] || 'info'
}

function statusType(status) {
  const map = { open: 'danger', analyzing: 'warning', resolved: 'success' }
  return map[status] || 'info'
}

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
    if (res.trace_id) {
      ElMessage.success(`分析已提交，Trace ID: ${res.trace_id}`)
    } else if (res.attack_chain_id) {
      ElMessage.success(`分析完成，攻击链 ID: ${res.attack_chain_id}`)
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

  try {
    await store.fetchAlertDetail(row.id)
    if (store.currentAlert) {
      currentDetail.value = store.currentAlert
    }
  } catch {
  }
}

onMounted(() => {
  store.fetchAlerts()
})
</script>
