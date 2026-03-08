// @ts-check

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAlerts, getAlertDetail, analyzeAlerts, getAuditLogs } from '../api/index.js'

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

const DEFAULT_FILTERS = Object.freeze({
  severity: '',
  source: '',
  status: '',
  page: 1,
  limit: 20,
})

const POLL_MAX_WAIT = 60000
const POLL_INTERVAL = 5000

/**
 * @param {unknown} error
 * @returns {string}
 */
function getErrorMessage(error) {
  return error instanceof Error ? error.message : String(error)
}

/**
 * @returns {AlertFilters}
 */
function createDefaultFilters() {
  return { ...DEFAULT_FILTERS }
}

/**
 * @param {AlertFilters} filters
 * @returns {Record<string, string | number>}
 */
function buildAlertQueryParams(filters) {
  /** @type {Record<string, string | number>} */
  const params = {
    limit: filters.limit,
    offset: (filters.page - 1) * filters.limit,
  }

  if (filters.severity) params.severity = filters.severity
  if (filters.source) params.source = filters.source
  if (filters.status) params.status = filters.status

  return params
}

/**
 * @param {unknown} payload
 * @returns {Record<string, unknown> | null}
 */
function extractFinishedAnalysis(payload) {
  if (!payload || typeof payload !== 'object') return null

  const logs = Array.isArray(payload.logs) ? payload.logs : []
  const finished = logs.find(
    (/** @type {Record<string, unknown>} */ log) => log.event_type === 'analysis_finished'
  )

  if (!finished || typeof finished !== 'object') return null

  if (finished.data && typeof finished.data === 'object') {
    return /** @type {Record<string, unknown>} */ (finished.data)
  }

  return /** @type {Record<string, unknown>} */ (finished)
}

/**
 * @param {number[]} ids
 * @returns {number[]}
 */
function normalizeSelection(ids) {
  return [...new Set(ids.filter((id) => Number.isInteger(id)))]
}

/**
 * @param {(ms: number) => Promise<unknown>} sleep
 * @param {number} ms
 */
async function waitInterval(sleep, ms) {
  await sleep(ms)
}

export const useAlertStore = defineStore('alert', () => {
  const alerts = ref(/** @type {AlertRecord[]} */ ([]))
  const total = ref(0)
  const loading = ref(false)
  const currentAlert = ref(/** @type {AlertRecord | null} */ (null))
  const selectedIds = ref(/** @type {number[]} */ ([]))
  const filters = ref(createDefaultFilters())

  let listRequestToken = 0
  let detailRequestToken = 0

  /** @returns {Promise<void>} */
  async function fetchAlerts() {
    const requestToken = ++listRequestToken
    loading.value = true

    try {
      /** @type {AlertsResponse} */
      const res = await getAlerts(buildAlertQueryParams(filters.value))
      if (requestToken !== listRequestToken) return
      alerts.value = Array.isArray(res.alerts) ? res.alerts : []
      total.value = Number.isFinite(res.total) ? res.total : 0
    } catch (err) {
      if (requestToken !== listRequestToken) return
      console.error('Failed to fetch alerts:', getErrorMessage(err))
      alerts.value = []
      total.value = 0
    } finally {
      if (requestToken === listRequestToken) {
        loading.value = false
      }
    }
  }

  /** @param {number} id */
  async function fetchAlertDetail(id) {
    const requestToken = ++detailRequestToken
    currentAlert.value = null

    try {
      const detail = await getAlertDetail(id)
      if (requestToken !== detailRequestToken) return null
      currentAlert.value = detail
      return currentAlert.value
    } catch (err) {
      if (requestToken !== detailRequestToken) return null
      console.error('Failed to fetch alert detail:', getErrorMessage(err))
      currentAlert.value = null
      return null
    }
  }

  /** @returns {Promise<AnalysisResponse | null>} */
  async function submitAnalysis() {
    if (selectedIds.value.length === 0) return null
    try {
      return await analyzeAlerts(selectedIds.value)
    } catch (err) {
      console.error('Failed to submit analysis:', getErrorMessage(err))
      return null
    }
  }

  /**
   * Poll for analysis result completion.
   * @param {string} traceId
   * @param {{ maxWait?: number, interval?: number, sleep?: (ms: number) => Promise<unknown> }} [options]
   * @returns {Promise<Record<string, unknown> | null>}
   */
  async function pollAnalysisResult(traceId, options = {}) {
    const maxWait = options.maxWait ?? POLL_MAX_WAIT
    const interval = options.interval ?? POLL_INTERVAL
    const sleep = options.sleep ?? ((ms) => new Promise((resolve) => setTimeout(resolve, ms)))
    const deadline = Date.now() + maxWait

    ElMessage.info('正在等待分析完成...')

    while (Date.now() < deadline) {
      try {
        const finished = extractFinishedAnalysis(await getAuditLogs({ trace_id: traceId }))
        if (finished) return finished
      } catch (err) {
        console.error('Poll error:', getErrorMessage(err))
      }

      if (Date.now() + interval >= deadline) break
      await waitInterval(sleep, interval)
    }

    ElMessage.warning('分析轮询超时，请前往审计页面查看结果')
    return null
  }

  /** @param {Partial<AlertFilters>} newFilters */
  function setFilters(newFilters) {
    filters.value = {
      ...filters.value,
      ...newFilters,
    }
  }

  /** @param {number[]} ids */
  function toggleSelection(ids) {
    selectedIds.value = normalizeSelection(ids)
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
    pollAnalysisResult,
    setFilters,
    toggleSelection,
  }
})
