<template>
  <div>
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

    <el-card shadow="hover" class="filter-card">
      <div class="filter-summary">
        <div class="filter-summary-item">
          <strong>{{ store.total || 0 }}</strong>
          <span>当前结果总数</span>
        </div>
        <div class="filter-summary-item">
          <strong>{{ store.selectedIds.length }}</strong>
          <span>已选待分析告警</span>
        </div>
      </div>

      <el-form :inline="true" :model="store.filters" class="filter-form">
        <el-form-item label="等级">
          <el-select v-model="store.filters.severity" placeholder="全部" clearable style="width: 140px">
            <el-option label="Critical" value="critical" />
            <el-option label="High" value="high" />
            <el-option label="Medium" value="medium" />
            <el-option label="Low" value="low" />
          </el-select>
        </el-form-item>

        <el-form-item label="来源">
          <el-select v-model="store.filters.source" placeholder="全部" clearable style="width: 140px">
            <el-option label="WAF" value="waf" />
            <el-option label="NIDS" value="nids" />
            <el-option label="HIDS" value="hids" />
            <el-option label="SOC" value="soc" />
          </el-select>
        </el-form-item>

        <el-form-item label="状态">
          <el-select v-model="store.filters.status" placeholder="全部" clearable style="width: 140px">
            <el-option label="Open" value="open" />
            <el-option label="Analyzing" value="analyzing" />
            <el-option label="Analyzed" value="analyzed" />
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

    <div class="toolbar-row">
      <div class="metric-chip">Selected {{ store.selectedIds.length }}</div>
      <el-button
        type="warning"
        :disabled="store.selectedIds.length === 0"
        @click="handleAnalyze"
      >
        <el-icon><MagicStick /></el-icon>
        AI 分析 ({{ store.selectedIds.length }})
      </el-button>
    </div>

    <el-card shadow="hover">
      <el-table
        :data="store.alerts"
        v-loading="store.loading"
        stripe
        class="data-table"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column prop="severity" label="等级" width="100">
          <template #default="{ row }">
            <el-tag :type="getSeverityTagType(row.severity)" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="告警标题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="src_ip" label="源IP" width="140" />
        <el-table-column prop="dst_ip" label="目标IP" width="140" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
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
    </el-card>

    <el-dialog v-model="detailVisible" title="告警详情" width="680px">
      <el-descriptions :column="2" border v-if="currentDetail">
        <el-descriptions-item label="ID">{{ currentDetail.id }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ currentDetail.source }}</el-descriptions-item>
        <el-descriptions-item label="等级">
          <el-tag :type="getSeverityTagType(currentDetail.severity)" size="small">
            {{ currentDetail.severity }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">{{ currentDetail.status }}</el-descriptions-item>
        <el-descriptions-item label="标题" :span="2">{{ currentDetail.title }}</el-descriptions-item>
        <el-descriptions-item label="源IP">{{ currentDetail.src_ip }}</el-descriptions-item>
        <el-descriptions-item label="目标IP">{{ currentDetail.dst_ip }}</el-descriptions-item>
        <el-descriptions-item label="时间" :span="2">{{ currentDetail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="原始数据" :span="2">
          <pre class="detail-pre">{{ JSON.stringify(currentDetail.raw_data || currentDetail, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
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
.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}
</style>
