// @ts-check

import axios from 'axios'
import { ElMessage } from 'element-plus'
import { ref } from 'vue'

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

/** Global loading counter - can be used by components to show loading indicators */
export const activeRequests = ref(0)

/**
 * Convert a camelCase string to snake_case.
 * @param {string} str
 * @returns {string}
 */
function toSnakeCase(str) {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

/**
 * Recursively convert object keys from camelCase to snake_case.
 * Suitable for transforming request payloads to match Python/FastAPI conventions.
 * @param {unknown} obj
 * @returns {unknown}
 */
function keysToSnakeCase(obj) {
  if (Array.isArray(obj)) return obj.map(keysToSnakeCase)
  if (obj !== null && typeof obj === 'object' && !(obj instanceof Date)) {
    return Object.fromEntries(
      Object.entries(obj).map(([key, value]) => [toSnakeCase(key), keysToSnakeCase(value)])
    )
  }
  return obj
}

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  // Transform request data: convert camelCase keys to snake_case for FastAPI
  transformRequest: [
    (data, headers) => {
      if (data && typeof data === 'object' && !(data instanceof FormData)) {
        return JSON.stringify(keysToSnakeCase(data))
      }
      return data
    },
  ],
})

/**
 * Request interceptor: attach auth token if available and track loading state.
 */
http.interceptors.request.use(
  (config) => {
    activeRequests.value++

    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }

    return config
  },
  (error) => {
    activeRequests.value = Math.max(0, activeRequests.value - 1)
    return Promise.reject(error)
  }
)

/**
 * Extract a human-readable error message from an API error response payload.
 * Handles FastAPI's standard { detail: "..." } format as well as { message: "..." }.
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
 * Response interceptor: unwrap response data and handle errors with ElMessage.
 */
http.interceptors.response.use(
  (res) => {
    activeRequests.value = Math.max(0, activeRequests.value - 1)
    return res.data
  },
  (err) => {
    activeRequests.value = Math.max(0, activeRequests.value - 1)
    console.error('API Error:', err)

    const response = err?.response
    const status = response?.status
    const message = extractErrorMessage(response?.data)

    if (status === 401) {
      ElMessage.error(message || '认证已过期，请重新登录')
      localStorage.removeItem('auth_token')
    } else if (status === 403) {
      ElMessage.error(message || '权限不足')
    } else if (status === 404) {
      // Silently handle 404 - callers can decide whether to show a message
    } else if (status === 422) {
      // FastAPI validation error
      ElMessage.error(message || '请求参数验证失败')
    } else if (status === 400 && message) {
      ElMessage.error(message)
    } else if (status && status >= 500) {
      ElMessage.error(message || '服务器内部错误，请稍后重试')
    } else if (!response) {
      ElMessage.error('网络连接失败，请检查网络')
    }

    return Promise.reject(err)
  }
)

// ============================================================
// Dashboard
// ============================================================

/**
 * Check backend health status.
 * @returns {Promise<{ status: string, timestamp?: string }>}
 */
export const getBackendHealth = () => http.get('/health')

/**
 * Get the current agent status including MCP connection info.
 * @returns {Promise<{ status: string, mcp_connected?: boolean, mcp_servers?: string[], running_tasks?: number, db_path?: string }>}
 */
export const getAgentStatus = () => http.get('/analysis/agent/status')

/**
 * Fetch aggregated dashboard statistics.
 * @returns {Promise<{ summary?: Record<string, number>, alerts_by_severity?: Array<{ severity: string, count: number }> }>}
 */
export const getDashboardStats = () => http.get('/dashboard/stats')

/**
 * Fetch alert trend data for the dashboard chart.
 * @returns {Promise<{ trend?: Array<{ date?: string, hour?: string, count?: number }> }>}
 */
export const getDashboardTrend = () => http.get('/dashboard/trend')

// ============================================================
// Alerts
// ============================================================

/**
 * Fetch a paginated list of alerts, optionally filtered.
 * @param {AlertQueryParams} params - Query parameters for filtering and pagination
 * @returns {Promise<AlertsResponse>}
 */
export const getAlerts = (params) => http.get('/alerts', { params })

/**
 * Fetch detailed information for a single alert.
 * @param {number | string} id - The alert ID
 * @returns {Promise<AlertRecord>}
 */
export const getAlertDetail = (id) => http.get(`/alerts/${id}`)

// ============================================================
// Analysis
// ============================================================

/**
 * Submit selected alerts for AI-powered analysis.
 * @param {number[]} alertIds - Array of alert IDs to analyze
 * @returns {Promise<AnalysisResponse>}
 */
export const analyzeAlerts = (alertIds) =>
  http.post('/analysis/alerts', { alert_ids: alertIds })

/**
 * Send a conversation to the AI chat endpoint.
 * @param {ChatMessage[]} messages - Array of chat messages
 * @returns {Promise<{ reply: string | null }>}
 */
export const chatWithAI = (messages) =>
  http.post('/analysis/chat', { messages })

/**
 * Fetch all attack chains discovered by the analysis engine.
 * @returns {Promise<{ chains: Array<Record<string, unknown>> }>}
 */
export const getAttackChains = () => http.get('/analysis/chains')

/**
 * Update the status of a decision (approve/reject/execute).
 * @param {number | string} id - The decision ID
 * @param {string} status - The new status value
 * @returns {Promise<unknown>}
 */
export const updateDecision = (id, status) =>
  http.patch(`/analysis/decisions/${id}`, { status })

// ============================================================
// Approval
// ============================================================

/**
 * Fetch approval requests, optionally filtered by status.
 * @param {Record<string, string | number>} params - Query parameters (e.g., { status: 'pending' })
 * @returns {Promise<{ approvals: Array<Record<string, unknown>> }>}
 */
export const getApprovals = (params) => http.get('/approval', { params })

/**
 * Respond to an approval request (approve or reject).
 * @param {number | string} id - The approval request ID
 * @param {string} status - 'approved' or 'rejected'
 * @param {string} [reason] - Optional reason for rejection
 * @returns {Promise<unknown>}
 */
export const respondApproval = (id, status, reason) =>
  http.patch(`/approval/${id}`, { status, reason })

// ============================================================
// MCP
// ============================================================

/**
 * List all connected MCP servers.
 * @returns {Promise<{ servers: Array<Record<string, unknown>> }>}
 */
export const getMcpServers = () => http.get('/analysis/mcp/servers')

// ============================================================
// Audit
// ============================================================

/**
 * Fetch audit/agent logs, optionally filtered by trace_id.
 * @param {Record<string, string | number>} params - Query parameters (e.g., { trace_id: '...' })
 * @returns {Promise<AuditLogsResponse>}
 */
export const getAuditLogs = (params) => http.get('/audit', { params })

/**
 * Fetch aggregated audit statistics (token usage, analysis counts).
 * @param {Record<string, string | number>} [params] - Optional query parameters (e.g., { days: 7 })
 * @returns {Promise<AuditStatsResponse>}
 */
export const getAuditStats = (params = {}) => http.get('/audit/stats', { params })

// ============================================================
// Notifications
// ============================================================

/**
 * Fetch all configured notification channels.
 * @returns {Promise<{ channels: Array<Record<string, unknown>> }>}
 */
export const getNotificationChannels = () => http.get('/notifications/channels')

/**
 * Create or update a notification channel.
 * @param {Record<string, unknown>} data - Channel configuration data
 * @returns {Promise<Record<string, unknown>>}
 */
export const saveNotificationChannel = (data) => http.post('/notifications/channels', data)

/**
 * Send a test notification through a specific channel.
 * @param {number | string} id - The channel ID
 * @returns {Promise<{ success: boolean }>}
 */
export const testNotificationChannel = (id) => http.post(`/notifications/channels/${id}/test`)

/**
 * Delete a notification channel.
 * @param {number | string} id - The channel ID
 * @returns {Promise<unknown>}
 */
export const deleteNotificationChannel = (id) => http.delete(`/notifications/channels/${id}`)

/**
 * Fetch all notification rules.
 * @returns {Promise<{ rules: Array<Record<string, unknown>> }>}
 */
export const getNotificationRules = () => http.get('/notifications/rules')

/**
 * Create or update a notification rule.
 * @param {Record<string, unknown>} data - Rule configuration data
 * @returns {Promise<Record<string, unknown>>}
 */
export const saveNotificationRule = (data) => http.put('/notifications/rules', data)

/**
 * Fetch notification send history.
 * @param {Record<string, string | number>} [params] - Optional pagination/filter parameters
 * @returns {Promise<{ history: Array<Record<string, unknown>>, total?: number }>}
 */
export const getNotificationHistory = (params) => http.get('/notifications/history', { params })

// ============================================================
// Settings (system_config table)
// ============================================================

/**
 * Fetch all system configuration entries.
 * @returns {Promise<{ configs: Array<{ key: string, value: string }> }>}
 */
export const getSettings = () => http.get('/config')

/**
 * Update system configuration entries.
 * @param {Record<string, string>} data - Key-value pairs to update
 * @returns {Promise<unknown>}
 */
export const updateSettings = (data) => http.put('/config', data)

export default http
