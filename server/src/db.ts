import Database from 'better-sqlite3'
import path from 'path'

const DB_PATH = process.env.DATABASE_URL || path.join(__dirname, '../../db/seo.db')

let _db: Database.Database | null = null

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH)
    _db.pragma('journal_mode = WAL')
    _db.pragma('foreign_keys = ON')
  }
  return _db
}

export function setDb(db: Database.Database): void {
  _db = db
}

export function migrate(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS clients (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      slug TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      site_url TEXT NOT NULL,
      sector TEXT,
      notify_email TEXT,
      client_static_token TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT,
      role TEXT NOT NULL CHECK(role IN ('superadmin','client','collaborator')),
      client_id INTEGER REFERENCES clients(id),
      magic_link_token TEXT,
      magic_link_expires_at TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      client_id INTEGER NOT NULL REFERENCES clients(id),
      run_date TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','published')),
      audit_seo TEXT,
      audit_geo TEXT,
      audit_aeo TEXT,
      fixes TEXT,
      pages_audit TEXT,
      report_md TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      published_at TEXT,
      UNIQUE(client_id, run_date)
    );

    CREATE TABLE IF NOT EXISTS fix_interactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id INTEGER NOT NULL REFERENCES runs(id),
      fix_key TEXT NOT NULL,
      user_id INTEGER NOT NULL REFERENCES users(id),
      status TEXT NOT NULL CHECK(status IN ('seen','in_progress','done')),
      comment TEXT,
      updated_at TEXT DEFAULT (datetime('now')),
      synced_at TEXT,
      UNIQUE(run_id, fix_key)
    );

    CREATE TABLE IF NOT EXISTS run_triggers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      client_id INTEGER NOT NULL REFERENCES clients(id),
      run_type TEXT NOT NULL CHECK(run_type IN ('full','seo','geo','aeo')),
      created_by INTEGER NOT NULL REFERENCES users(id),
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','done','failed')),
      notes TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      picked_up_at TEXT,
      done_at TEXT
    );

    CREATE TABLE IF NOT EXISTS local_sync_cursors (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      client_slug TEXT UNIQUE NOT NULL,
      last_pulled_at TEXT
    );

    CREATE TABLE IF NOT EXISTS notifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id),
      type TEXT NOT NULL,
      client_id INTEGER REFERENCES clients(id),
      run_id INTEGER REFERENCES runs(id),
      fix_key TEXT,
      read_at TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS api_tokens (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      label TEXT NOT NULL,
      token_hash TEXT NOT NULL UNIQUE,
      created_at TEXT DEFAULT (datetime('now')),
      last_used_at TEXT
    );
  `)
  // Idempotent column additions (safe on existing DBs)
  try { db.exec(`ALTER TABLE runs ADD COLUMN audit_schema TEXT`) } catch (_) {}
  try { db.exec(`ALTER TABLE runs ADD COLUMN audit_llm TEXT`) } catch (_) {}
}
