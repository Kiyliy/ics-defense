/**
 * 请求体校验中间件
 * @param {Object} schema - { field: { type: 'string'|'number'|'array', required: boolean } }
 */
export function validateBody(schema) {
  return (req, res, next) => {
    const errors = [];
    for (const [field, rules] of Object.entries(schema)) {
      const value = req.body[field];
      if (rules.required && (value === undefined || value === null)) {
        errors.push(`${field} is required`);
        continue;
      }
      if (value !== undefined && value !== null) {
        if (rules.type === 'array' && !Array.isArray(value)) {
          errors.push(`${field} must be an array`);
        } else if (rules.type === 'string' && typeof value !== 'string') {
          errors.push(`${field} must be a string`);
        } else if (rules.type === 'number' && typeof value !== 'number') {
          errors.push(`${field} must be a number`);
        }
      }
    }
    if (errors.length > 0) {
      return res.status(400).json({ error: 'Validation failed', details: errors });
    }
    next();
  };
}
