import Database from 'better-sqlite3'
import bcrypt from 'bcryptjs'
import crypto from 'crypto'
import jwt from 'jsonwebtoken'
import { migrate, setDb } from '../src/db'
import { JwtPayload } from '../src/types'

export const TEST_JWT_SECRET = 'test-secret-32-chars-minimum-ok'

export function createTestDb(): Database.Database {
  const db = new Database(':memory:')
  db.pragma('journal_mode = WAL')
  db.pragma('foreign_keys = ON')
  migrate(db)
  setDb(db)
  return db
}

export function createClient(db: Database.Database, slug = 'test-client') {
  return db.prepare(
    `INSERT INTO clients (slug, name, site_url) VALUES (?, ?, ?) RETURNING *`
  ).get(slug, 'Test Client', 'https://test.com') as any
}

export function createUser(
  db: Database.Database,
  email: string,
  role: 'superadmin' | 'client' | 'collaborator',
  clientId: number | null = null
) {
  const hash = bcrypt.hashSync('password123', 10)
  return db.prepare(
    `INSERT INTO users (email, password_hash, role, client_id) VALUES (?, ?, ?, ?) RETURNING *`
  ).get(email, hash, role, clientId) as any
}

export function getToken(user: any): string {
  const payload: JwtPayload = {
    userId: user.id,
    email: user.email,
    role: user.role,
    clientId: user.client_id
  }
  return jwt.sign(payload, TEST_JWT_SECRET, { expiresIn: '7d' })
}

export function createApiToken(db: Database.Database, label = 'watcher'): string {
  const raw = crypto.randomBytes(32).toString('hex')
  const hash = crypto.createHash('sha256').update(raw).digest('hex')
  db.prepare(`INSERT INTO api_tokens (label, token_hash) VALUES (?, ?)`).run(label, hash)
  return raw
}
