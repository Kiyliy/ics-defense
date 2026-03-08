// @ts-check

const isProduction = (process.env.NODE_ENV || 'development') === 'production';

/**
 * Sanitize error messages to prevent internal detail leakage in production.
 * @param {string} message
 * @returns {string}
 */
function sanitizeMessage(message) {
  if (!isProduction) return message;

  // Hide database, file-system, and internal errors from clients
  const sensitivePatterns = [
    /SQLITE_/i,
    /ENOENT/i,
    /ECONNREFUSED/i,
    /no such table/i,
    /\/[\w/]+\.\w+/,       // file paths
    /at\s+\w+\s+\(/,       // stack-like fragments
  ];

  for (const pattern of sensitivePatterns) {
    if (pattern.test(message)) {
      return 'Internal Server Error';
    }
  }

  return message;
}

export function errorHandler(err, req, res, next) {
  console.error(`[${new Date().toISOString()}] Error:`, err.message, err.stack || '');
  const status = err.status || err.statusCode || 500;
  res.status(status).json({
    error: sanitizeMessage(err.message || 'Internal Server Error'),
    ...(!isProduction && { stack: err.stack }),
  });
}
