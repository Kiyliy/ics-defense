/**
 * @param {string | null | undefined} severity
 * @returns {string}
 */
export function getSeverityTagType(severity) {
  const normalized = String(severity || '').toLowerCase()
  const map = {
    critical: 'danger',
    error: 'warning',
    high: 'warning',
    warning: '',
    medium: '',
    info: 'info',
    low: 'info',
    resolved: 'success',
  }
  return map[normalized] || 'info'
}

/**
 * @param {string | null | undefined} level
 * @returns {string}
 */
export function getRiskTagType(level) {
  const normalized = String(level || '').toLowerCase()
  const map = {
    critical: 'danger',
    high: 'danger',
    medium: 'warning',
    warning: 'warning',
    low: 'success',
    info: 'info',
  }
  return map[normalized] || 'info'
}

/**
 * @param {string | null | undefined} status
 * @returns {string}
 */
export function getStatusTagType(status) {
  const normalized = String(status || '').toLowerCase()
  const map = {
    open: 'danger',
    analyzing: 'warning',
    analyzed: '',
    pending: 'warning',
    accepted: 'success',
    approved: 'success',
    rejected: 'danger',
    resolved: 'success',
  }
  return map[normalized] || 'info'
}
