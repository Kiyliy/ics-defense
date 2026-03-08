import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { initDB } from '../src/models/db.js';

test('initDB creates schema tables and indexes', () => {
  const tempDir = mkdtempSync(join(tmpdir(), 'ics-defense-db-'));
  const dbPath = join(tempDir, 'nested', 'test.db');

  try {
    const db = initDB(dbPath);
    const tables = db.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all();
    const names = new Set(tables.map((row) => row.name));

    assert.ok(names.has('assets'));
    assert.ok(names.has('raw_events'));
    assert.ok(names.has('alerts'));
    assert.ok(names.has('attack_chains'));
    assert.ok(names.has('decisions'));
    assert.ok(names.has('approval_queue'));
    assert.ok(names.has('audit_logs'));

    const indexes = db.prepare("SELECT name FROM sqlite_master WHERE type = 'index'").all();
    const indexNames = new Set(indexes.map((row) => row.name));
    assert.ok(indexNames.has('idx_alerts_status'));
    assert.ok(indexNames.has('idx_approval_status'));

    db.close();
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});
