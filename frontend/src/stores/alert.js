// @ts-check

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAlerts, getAlertDetail, analyzeAlerts } from '../api/index.js'

/** @typedef {import('../api/index.js').AlertRecord} AlertRecord */
/** @typedef {import('../api/index.js').AlertsResponse} AlertsResponse */
/** @typedef {import('../api/index.js').AnalysisResponse} AnalysisResponse */

/**
 * @typedef {{
 *   severity: string
 *   source: string
 *   status: string
 *   page: number
 *   limit: number
 * }} AlertFilters
 */

/**
 * @param {unknown} error
 * @returns {string}
 */
function getErrorMessage(error) {
  return error instanceof Error ? error.message : String(error)
}

export const useAlertStore = defineStore('alert', () => {
  const alerts = ref(/** @type {AlertRecord[]} */ ([]))
  const total = ref(0)
  const loading = ref(false)
  const currentAlert = ref(/** @type {AlertRecord | null} */ (null))
  const selectedIds = ref(/** @type {number[]} */ ([]))

  const filters = ref(/** @type {AlertFilters} */ ({
    severity: '',
    source: '',
    status: '',
    page: 1,
    limit: 20,
  }))

  /** @returns {Promise<void>} */
  async function fetchAlerts() {
    loading.value = true
    try {
      /** @type {Record<string, string | number>} */
      const params = {}
      if (filters.value.severity) params.severity = filters.value.severity
      if (filters.value.source) params.source = filters.value.source
      if (filters.value.status) params.status = filters.value.status
      params.page = filters.value.page
      params.limit = filters.value.limit

      /** @type {AlertsResponse} */
      const res = await getAlerts(params)
      alerts.value = res.alerts || []
      total.value = res.total || 0
    } catch (err) {
      console.error('Failed to fetch alerts:', getErrorMessage(err))
      alerts.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  /** @param {number} id */
  async function fetchAlertDetail(id) {
    try {
      currentAlert.value = await getAlertDetail(id)
    } catch (err) {
      console.error('Failed to fetch alert detail:', getErrorMessage(err))
    }
  }

  /** @returns {Promise<AnalysisResponse | null>} */
  async function submitAnalysis() {
    if (selectedIds.value.length === 0) return null
    try {
      const res = await analyzeAlerts(selectedIds.value)
      return res
    } catch (err) {
      console.error('Failed to submit analysis:', getErrorMessage(err))
      return null
    }
  }

  /** @param {Partial<AlertFilters>} newFilters */
  function setFilters(newFilters) {
    Object.assign(filters.value, newFilters)
  }

  /** @param {number[]} ids */
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
