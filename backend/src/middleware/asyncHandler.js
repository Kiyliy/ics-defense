// @ts-check

/**
 * Wraps an async route handler so that rejected promises are forwarded to
 * Express error-handling middleware (errorHandler) instead of causing
 * an unhandled rejection.
 *
 * @param {Function} fn
 * @returns {import('express').RequestHandler}
 */
export function asyncHandler(fn) {
  return (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}
