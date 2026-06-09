import { createTestDb, createClient, createUser } from './helpers'
import request from 'supertest'
import express from 'express'
import jwt from 'jsonwebtoken'
import { requireAuth } from '../src/middleware/auth'
import { requireApiToken } from '../src/middleware/apiToken'
import { createApiToken, TEST_JWT_SECRET } from './helpers'

process.env.JWT_SECRET = TEST_JWT_SECRET

describe('migrate()', () => {
  it('creates all tables without error', () => {
    const db = createTestDb()
    const tables = db.prepare(
      `SELECT name FROM sqlite_master WHERE type='table' ORDER BY name`
    ).all().map((r: any) => r.name)
    expect(tables).toEqual(expect.arrayContaining([
      'api_tokens', 'clients', 'fix_interactions',
      'local_sync_cursors', 'notifications', 'run_triggers',
      'runs', 'users'
    ]))
  })

  it('createClient() inserts and returns a client', () => {
    const db = createTestDb()
    const client = createClient(db)
    expect(client.slug).toBe('test-client')
  })
})

describe('requireAuth()', () => {
  const app = express()
  app.get('/protected', requireAuth(), (req, res) => res.json({ ok: true }))
  app.get('/admin-only', requireAuth('superadmin'), (req, res) => res.json({ ok: true }))

  it('returns 401 with no token', async () => {
    const res = await request(app).get('/protected')
    expect(res.status).toBe(401)
  })

  it('returns 200 with valid token', async () => {
    const token = jwt.sign(
      { userId: 1, email: 'a@b.com', role: 'client', clientId: 1 },
      TEST_JWT_SECRET
    )
    const res = await request(app).get('/protected').set('Authorization', `Bearer ${token}`)
    expect(res.status).toBe(200)
  })

  it('returns 403 when role does not match', async () => {
    const token = jwt.sign(
      { userId: 1, email: 'a@b.com', role: 'client', clientId: 1 },
      TEST_JWT_SECRET
    )
    const res = await request(app).get('/admin-only').set('Authorization', `Bearer ${token}`)
    expect(res.status).toBe(403)
  })
})

describe('requireApiToken()', () => {
  let db: ReturnType<typeof createTestDb>
  const app = express()
  app.get('/api', requireApiToken, (req, res) => res.json({ ok: true }))

  beforeEach(() => { db = createTestDb() })

  it('returns 401 with no token', async () => {
    const res = await request(app).get('/api')
    expect(res.status).toBe(401)
  })

  it('returns 200 with valid API token', async () => {
    const raw = createApiToken(db)
    const res = await request(app).get('/api').set('Authorization', `Bearer ${raw}`)
    expect(res.status).toBe(200)
  })

  it('returns 401 with wrong token', async () => {
    createApiToken(db)
    const res = await request(app).get('/api').set('Authorization', 'Bearer wrong-token')
    expect(res.status).toBe(401)
  })
})
