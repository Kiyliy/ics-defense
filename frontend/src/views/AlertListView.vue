<template>
  <div class="alert-view">
    <PageBanner title="告警列表" subtitle="统一查看全域告警、按风险与来源快速过滤，并将关键事件直接送入 AI 研判与攻击链分析流程。">
      <template #right>
        <span>Alert Triage</span>
        <span>{{ store.total || 0 }} Total Records</span>
      </template>
    </PageBanner>

    <AlertFilters
      :filters="store.filters"
      @search="handleSearch"
      @reset="handleReset"
    />

    <AlertTable
      :alerts="store.alerts"
      :loading="store.loading"
      :total="store.total"
      :page="store.filters.page"
      :pageSize="store.filters.limit"
      @selection-change="handleSelectionChange"
      @show-detail="showDetail"
      @update:page="store.filters.page = $event; handleSearch()"
      @update:pageSize="store.filters.limit = $event; handleSearch()"
    />

    <SelectionToolbar
      :count="store.selectedIds.length"
      @analyze="handleAnalyze"
    />

    <AlertDetailDrawer
      :visible="detailVisible"
      :detail="currentDetail"
      @update:visible="detailVisible = $event"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PageBanner from '../components/layout/PageBanner.vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAlertStore } from '../stores/alert'
import AlertFilters from '../components/alerts/AlertFilters.vue'
import AlertTable from '../components/alerts/AlertTable.vue'
import AlertDetailDrawer from '../components/alerts/AlertDetailDrawer.vue'
import SelectionToolbar from '../components/alerts/SelectionToolbar.vue'

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
.alert-view {
  display: flex;
  flex-direction: column;
}
</style>
