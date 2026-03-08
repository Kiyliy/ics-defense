import axios from 'axios'

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
export const getDashboardStats = () => http.get('/dashboard/stats')
export const getDashboardTrend = () => http.get('/dashboard/trend')

// Alerts
export const getAlerts = (params) => http.get('/alerts', { params })
export const getAlertDetail = (id) => http.get(`/alerts/${id}`)

// Analysis
export const analyzeAlerts = (alertIds) =>
  http.post('/analysis/alerts', { alert_ids: alertIds })
export const chatWithAI = (messages) =>
  http.post('/analysis/chat', { messages })
export const getAttackChains = () => http.get('/analysis/chains')
export const updateDecision = (id, status) =>
  http.patch(`/analysis/decisions/${id}`, { status })

// Approval
export const getApprovals = (params) => http.get('/approval', { params })
export const respondApproval = (id, status, reason) =>
  http.post(`/approval/${id}/respond`, { status, reason })

// Audit
export const getAuditLogs = (params) => http.get('/audit', { params })
export const getAuditStats = () => http.get('/audit/stats')

export default http
