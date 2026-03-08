// @ts-check

import axios from 'axios'

/**
 * @typedef {'low' | 'medium' | 'high' | 'critical' | 'unknown'} RiskLevel
 */

/**
 * @typedef {'open' | 'analyzing' | 'closed' | 'ignored' | string} AlertStatus
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
 *   page?: number
 *   limit?: number
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

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('API Error:', err)
    return Promise.reject(err)
  }
)

// Dashboard
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
  unwrap(http.post(`/approval/${id}/respond`, { status, reason }))

// Audit
/** @param {Record<string, string | number>} params */
export const getAuditLogs = (params) => unwrap(http.get('/audit', { params }))
export const getAuditStats = () => unwrap(http.get('/audit/stats'))

export default http
