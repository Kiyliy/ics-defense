import { describe, it, expect } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { initDB } from '../src/models/db.js';

describe('database initialization', () => {
  it('initDB creates schema tables and indexes', () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'ics-defense-db-'));
    const dbPath = join(tempDir, 'nested', 'test.db');

    try {
      const db = initDB(dbPath);
      const tables = db.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all();
      const names = new Set(tables.map((row) => row.name));

      expect(names.has('assets')).toBe(true);
      expect(names.has('raw_events')).toBe(true);
      expect(names.has('alerts')).toBe(true);
      expect(names.has('attack_chains')).toBe(true);
      expect(names.has('decisions')).toBe(true);
      expect(names.has('approval_queue')).toBe(true);
      expect(names.has('audit_logs')).toBe(true);

      const indexes = db.prepare("SELECT name FROM sqlite_master WHERE type = 'index'").all();
      const indexNames = new Set(indexes.map((row) => row.name));
      expect(indexNames.has('idx_alerts_status')).toBe(true);
      expect(indexNames.has('idx_approval_status')).toBe(true);

      db.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });
});
