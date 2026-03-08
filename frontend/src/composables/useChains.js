import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAttackChains, updateDecision } from '../api'
import { normalizeAttackChain } from '../api/view-models.js'

export function useChains() {
  const chains = ref([])
  const loading = ref(false)
  const expandedId = ref(null)

  function toggleExpand(id) {
    expandedId.value = expandedId.value === id ? null : id
  }

  function normalizeRisk(level) {
    return String(level || 'unknown').toLowerCase()
  }

  async function fetchChains() {
    loading.value = true
    try {
      const res = await getAttackChains()
      chains.value = (res.chains || []).map(normalizeAttackChain)
    } catch (err) {
      console.error('Failed to fetch chains:', err)
    } finally {
      loading.value = false
    }
  }

  async function handleDecision(decisionId, status) {
    try {
      await updateDecision(decisionId, status)
      ElMessage.success('决策已更新')
      await fetchChains()
    } catch (err) {
      ElMessage.error('操作失败')
    }
  }

  return {
    chains,
    loading,
    expandedId,
    toggleExpand,
    normalizeRisk,
    fetchChains,
    handleDecision
  }
}
