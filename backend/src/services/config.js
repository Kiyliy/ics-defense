// @ts-check

/**
 * 系统配置服务 — 从 system_config 表读取业务参数，带内存缓存。
 *
 * 设计原则：
 *   - 部署/基础设施参数（PORT, DB_PATH, API_AUTH_TOKEN, REDIS_URL 等）留在环境变量
 *   - 可运行时调整的业务参数（速率限制、批量大小等）存在 DB，通过 API 修改
 */

/** @type {Map<string, string>} */
let cache = new Map();

/** @type {any} */
let _db = null;

/**
 * 初始化配置服务，绑定数据库实例并加载全部配置到内存
 * @param {any} db - better-sqlite3 实例
 */
export function initConfigService(db) {
  _db = db;
  reloadCache();
}

/**
 * 从数据库重新加载全部配置到内存缓存
 */
export function reloadCache() {
  if (!_db) return;
  const rows = _db.prepare('SELECT key, value FROM system_config').all();
  cache = new Map(rows.map((/** @type {any} */ r) => [r.key, r.value]));
}

/**
 * 获取配置值（从缓存读取）
 * @param {string} key
 * @param {string} [defaultValue]
 * @returns {string}
 */
export function getConfig(key, defaultValue = '') {
  return cache.get(key) ?? defaultValue;
}

/**
 * 获取配置值（数字）
 * @param {string} key
 * @param {number} defaultValue
 * @returns {number}
 */
export function getConfigInt(key, defaultValue = 0) {
  const raw = cache.get(key);
  if (raw === undefined) return defaultValue;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? n : defaultValue;
}

/**
 * 设置配置值（写入数据库并更新缓存）
 * @param {string} key
 * @param {string} value
 */
export function setConfig(key, value) {
  if (!_db) throw new Error('Config service not initialized');
  _db.prepare(
    `UPDATE system_config SET value = ?, updated_at = datetime('now') WHERE key = ?`
  ).run(value, key);
  cache.set(key, value);
}

/**
 * 获取全部配置（含描述，用于 API 返回）
 * @returns {Array<{ key: string, value: string, description: string, updated_at: string }>}
 */
export function getAllConfig() {
  if (!_db) return [];
  return _db.prepare('SELECT key, value, description, updated_at FROM system_config ORDER BY key').all();
}

/**
 * 批量更新配置
 * @param {Record<string, string>} entries
 * @returns {{ updated: string[], unknown: string[] }}
 */
export function batchSetConfig(entries) {
  if (!_db) throw new Error('Config service not initialized');

  const existingKeys = new Set(cache.keys());
  const updated = [];
  const unknown = [];

  const update = _db.prepare(
    `UPDATE system_config SET value = ?, updated_at = datetime('now') WHERE key = ?`
  );

  const runBatch = _db.transaction(() => {
    for (const [key, value] of Object.entries(entries)) {
      if (!existingKeys.has(key)) {
        unknown.push(key);
        continue;
      }
      update.run(String(value), key);
      cache.set(key, String(value));
      updated.push(key);
    }
  });

  runBatch();
  return { updated, unknown };
}
