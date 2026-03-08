// @ts-check

import axios from 'axios'

/**
 * @typedef {'low' | 'medium' | 'high' | 'critical' | 'unknown'} RiskLevel
 */

/**
 * @typedef {'open' | 'analyzing' | 'resolved' | string} AlertStatus
 */

/**
 * @typedef {{
 *   id: number
 *   title?: string
 *   description?: string
 *   severity?: string
 *   status?: AlertStatus
 *   source?: string
 *   created_at?: string
 * }} AlertRecord
 */

/**
 * @typedef {{
 *   severity?: string
 *   source?: string
 *   status?: string
 *   limit?: number
 *   offset?: number
 * }} AlertQueryParams
 */

/**
 * @typedef {{ alerts: AlertRecord[], total: number }} AlertsResponse
 */

/**
 * @typedef {{
 *   analysis?: string
 *   mitre_tactic?: string
 *   mitre_technique?: string
 *   risk_level?: RiskLevel
 *   confidence?: number
 *   recommendation?: string
 *   action_type?: string
 *   rationale?: string
 *   attack_chain_id?: number
 *   trace_id?: string
 *   status?: string
 *   message?: string
 * }} AnalysisResponse
 */

/**
 * @typedef {{ role: 'system' | 'user' | 'assistant', content: string }} ChatMessage
 */

/**
 * The response interceptor already extracts res.data, so http methods
 * resolve directly to the JSON payload. This helper just awaits the promise
 * for a uniform call-site style.
 *
 * @template T
 * @param {Promise<T>} request
 * @returns {Promise<T>}
 */
async function unwrap(request) {
  return await request
}

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

function resolveAgentStatusUrl() {
  if (typeof window === 'undefined') {
    return 'http://127.0.0.1:8000/status'
  }

  const { protocol, hostname } = window.location
  return `${protocol}//${hostname}:8000/status`
}

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('API Error:', err)
    return Promise.reject(err)
  }
)

// Dashboard
export const getBackendHealth = () => unwrap(http.get('/health'))

/**
 * @param {{ url?: string, fetchImpl?: typeof fetch }} [options]
 * @returns {Promise<{ status: string, mcp_connected?: boolean, mcp_servers?: string[], running_tasks?: number, db_path?: string }>}
 */
export async function getAgentStatus(options = {}) {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch
  if (typeof fetchImpl !== 'function') {
    throw new Error('fetch is unavailable in current environment')
  }

  const response = await fetchImpl(options.url ?? resolveAgentStatusUrl(), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`Agent status request failed with ${response.status}`)
  }

  return response.json()
}

export const getDashboardStats = () => unwrap(http.get('/dashboard/stats'))
export const getDashboardTrend = () => unwrap(http.get('/dashboard/trend'))

// Alerts
/**
 * @param {AlertQueryParams} params
 * @returns {Promise<AlertsResponse>}
 */
export const getAlerts = (params) => unwrap(http.get('/alerts', { params }))

/**
 * @param {number | string} id
 * @returns {Promise<AlertRecord>}
 */
export const getAlertDetail = (id) => unwrap(http.get(`/alerts/${id}`))

// Analysis
/**
 * @param {number[]} alertIds
 * @returns {Promise<AnalysisResponse>}
 */
export const analyzeAlerts = (alertIds) =>
  unwrap(http.post('/analysis/alerts', { alert_ids: alertIds }))

/**
 * @param {ChatMessage[]} messages
 * @returns {Promise<{ reply: string | null }>}
 */
export const chatWithAI = (messages) =>
  unwrap(http.post('/analysis/chat', { messages }))

export const getAttackChains = () => unwrap(http.get('/analysis/chains'))

/**
 * @param {number | string} id
 * @param {string} status
 */
export const updateDecision = (id, status) =>
  unwrap(http.patch(`/analysis/decisions/${id}`, { status }))

// Approval
/** @param {Record<string, string | number>} params */
export const getApprovals = (params) => unwrap(http.get('/approval', { params }))

/**
 * @param {number | string} id
 * @param {string} status
 * @param {string} reason
 */
export const respondApproval = (id, status, reason) =>
  unwrap(http.patch(`/approval/${id}`, { status, reason }))

// Audit
/** @param {Record<string, string | number>} params */
export const getAuditLogs = (params) => unwrap(http.get('/audit', { params }))

/** @param {Record<string, string | number>} [params] */
export const getAuditStats = (params = {}) => unwrap(http.get('/audit/stats', { params }))

export default http
