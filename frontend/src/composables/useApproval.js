import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApprovals, respondApproval } from '../api'

export function useApproval() {
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

  return {
    activeTab,
    approvals,
    loading,
    rejectDialogVisible,
    rejectReason,
    currentRejectItem,
    expandedArgs,
    allCount,
    pendingCount,
    toggleArgs,
    statusLabel,
    truncateArgs,
    formatArgs,
    fetchApprovals,
    handleApprove,
    handleReject,
    confirmReject
  }
}
