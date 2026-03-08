import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAlerts, getAlertDetail, analyzeAlerts } from '../api'

export const useAlertStore = defineStore('alert', () => {
  const alerts = ref([])
  const total = ref(0)
  const loading = ref(false)
  const currentAlert = ref(null)
  const selectedIds = ref([])

  const filters = ref({
    severity: '',
    source: '',
    status: '',
    page: 1,
    limit: 20,
  })

  async function fetchAlerts() {
    loading.value = true
    try {
      const params = {}
      if (filters.value.severity) params.severity = filters.value.severity
      if (filters.value.source) params.source = filters.value.source
      if (filters.value.status) params.status = filters.value.status
      params.page = filters.value.page
      params.limit = filters.value.limit

      const res = await getAlerts(params)
      alerts.value = res.alerts || []
      total.value = res.total || 0
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
      alerts.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  async function fetchAlertDetail(id) {
    try {
      currentAlert.value = await getAlertDetail(id)
    } catch (err) {
      console.error('Failed to fetch alert detail:', err)
    }
  }

  async function submitAnalysis() {
    if (selectedIds.value.length === 0) return null
    try {
      const res = await analyzeAlerts(selectedIds.value)
      return res
    } catch (err) {
      console.error('Failed to submit analysis:', err)
      return null
    }
  }

  function setFilters(newFilters) {
    Object.assign(filters.value, newFilters)
  }

  function toggleSelection(ids) {
    selectedIds.value = ids
  }

  return {
    alerts,
    total,
    loading,
    currentAlert,
    selectedIds,
    filters,
    fetchAlerts,
    fetchAlertDetail,
    submitAnalysis,
    setFilters,
    toggleSelection,
  }
})
