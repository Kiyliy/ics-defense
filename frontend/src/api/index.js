// @ts-check

import axios from 'axios'
import { ElMessage } from 'element-plus'

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
 * @typedef {{
 *   id?: number
 *   trace_id?: string
 *   event_type?: string
 *   data?: unknown
 *   token_usage?: string | null
 *   created_at?: string
 * }} AuditLogRecord
 */

/**
 * @typedef {{ logs: AuditLogRecord[], total: number }} AuditLogsResponse
 */

/**
 * @typedef {{
 *   total_analyses?: number
 *   total_input_tokens?: number
 *   total_output_tokens?: number
 *   daily?: Array<{ date: string, analyses: number, tokens: number }>
 * }} AuditStatsResponse
 */

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

/**
 * @param {unknown} payload
 * @returns {string | null}
 */
function extractErrorMessage(payload) {
  if (!payload) return null
  if (typeof payload === 'string') return payload
  if (typeof payload !== 'object') return null

  if ('detail' in payload && payload.detail) {
    return typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
  }

  if ('message' in payload && payload.message) {
    return String(payload.message)
  }

  return null
}

/**
 * @template T
 * @param {Promise<T>} requestPromise
 * @returns {Promise<T>}
 */
function request(requestPromise) {
  return requestPromise
}

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('API Error:', err)

    const response = err?.response
    const status = response?.status
    const message = extractErrorMessage(response?.data)

    if (status === 400 && message) {
      ElMessage.error(message)
    }

    return Promise.reject(err)
  }
)

// Dashboard
export const getBackendHealth = () => request(http.get('/health'))

/**
 * @returns {Promise<{ status: string, mcp_connected?: boolean, mcp_servers?: string[], running_tasks?: number, db_path?: string }>}
 */
export const getAgentStatus = () => request(http.get('/analysis/agent/status'))

export const getDashboardStats = () => request(http.get('/dashboard/stats'))
export const getDashboardTrend = () => request(http.get('/dashboard/trend'))

// Alerts
/**
 * @param {AlertQueryParams} params
 * @returns {Promise<AlertsResponse>}
 */
export const getAlerts = (params) => request(http.get('/alerts', { params }))

/**
 * @param {number | string} id
 * @returns {Promise<AlertRecord>}
 */
export const getAlertDetail = (id) => request(http.get(`/alerts/${id}`))

// Analysis
/**
 * @param {number[]} alertIds
 * @returns {Promise<AnalysisResponse>}
 */
export const analyzeAlerts = (alertIds) =>
  request(http.post('/analysis/alerts', { alert_ids: alertIds }))

/**
 * @param {ChatMessage[]} messages
 * @returns {Promise<{ reply: string | null }>}
 */
export const chatWithAI = (messages) =>
  request(http.post('/analysis/chat', { messages }))

export const getAttackChains = () => request(http.get('/analysis/chains'))

/**
 * @param {number | string} id
 * @param {string} status
 */
export const updateDecision = (id, status) =>
  request(http.patch(`/analysis/decisions/${id}`, { status }))

// Approval
/** @param {Record<string, string | number>} params */
export const getApprovals = (params) => request(http.get('/approval', { params }))

/**
 * @param {number | string} id
 * @param {string} status
 * @param {string} reason
 */
export const respondApproval = (id, status, reason) =>
  request(http.patch(`/approval/${id}`, { status, reason }))

// Audit
/**
 * @param {Record<string, string | number>} params
 * @returns {Promise<AuditLogsResponse>}
 */
export const getAuditLogs = (params) => request(http.get('/audit', { params }))

/**
 * @param {Record<string, string | number>} [params]
 * @returns {Promise<AuditStatsResponse>}
 */
export const getAuditStats = (params = {}) => request(http.get('/audit/stats', { params }))

export default http
