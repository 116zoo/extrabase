import request from 'supertest'
import express from 'express'
import { createTestDb, createClient, createUser, getToken, createApiToken, TEST_JWT_SECRET } from './helpers'
import fixesRouter from '../src/routes/fixes'

process.env.JWT_SECRET = TEST_JWT_SECRET

function buildApp() {
  const app = express()
  app.use(express.json())
  app.use('/api/fixes', fixesRouter)
  return app
}

describe('PATCH /api/fixes/:runId/:fixKey', () => {
  let db: any, client: any, clientUser: any, admin: any, runId: number, app: any

  beforeEach(() => {
    db = createTestDb()
    client = createClient(db)
    admin = createUser(db, 'admin@test.com', 'superadmin')
    clientUser = createUser(db, 'client@test.com', 'client', client.id)
    app = buildApp()
    const run = db.prepare(`INSERT INTO runs (client_id, run_date, status) VALUES (?, '2026-06-10', 'published') RETURNING id`).get(client.id) as any
    runId = run.id
  })

  it('client can update a fix status', async () => {
    const res = await request(app)
      .patch(`/api/fixes/${runId}/meta-title`)
      .set('Authorization', `Bearer ${getToken(clientUser)}`)
      .send({ status: 'in_progress', comment: 'Working on it' })
    expect(res.status).toBe(200)
    const fi = db.prepare(`SELECT * FROM fix_interactions WHERE run_id = ? AND fix_key = 'meta-title'`).get(runId) as any
    expect(fi.status).toBe('in_progress')
    expect(fi.comment).toBe('Working on it')
  })

  it('client cannot update fix for another client run', async () => {
    const other = createClient(db, 'other-client')
    const otherRun = db.prepare(`INSERT INTO runs (client_id, run_date, status) VALUES (?, '2026-06-10', 'published') RETURNING id`).get(other.id) as any
    const res = await request(app)
      .patch(`/api/fixes/${otherRun.id}/meta-title`)
      .set('Authorization', `Bearer ${getToken(clientUser)}`)
      .send({ status: 'done' })
    expect(res.status).toBe(403)
  })

  it('creates a notification for superadmin when client updates fix', async () => {
    await request(app)
      .patch(`/api/fixes/${runId}/meta-title`)
      .set('Authorization', `Bearer ${getToken(clientUser)}`)
      .send({ status: 'done' })
    const notif = db.prepare(`SELECT * FROM notifications WHERE user_id = ?`).get(admin.id) as any
    expect(notif).toBeDefined()
    expect(notif.type).toBe('fix_updated')
  })
})

describe('POST /api/fixes/bulk-sync', () => {
  let db: any, apiToken: string, runId: number, app: any

  beforeEach(() => {
    db = createTestDb()
    const client = createClient(db)
    createUser(db, 'admin@test.com', 'superadmin')
    apiToken = createApiToken(db)
    app = buildApp()
    const run = db.prepare(`INSERT INTO runs (client_id, run_date) VALUES (?, '2026-06-10') RETURNING id`).get(client.id) as any
    runId = run.id
  })

  it('bulk inserts fix interactions idempotently', async () => {
    const interactions = [
      { fix_key: 'meta-title', status: 'done' },
      { fix_key: 'h1-missing', status: 'in_progress', comment: 'fixing' }
    ]
    await request(app).post('/api/fixes/bulk-sync').set('Authorization', `Bearer ${apiToken}`).send({ run_id: runId, interactions })
    const res = await request(app).post('/api/fixes/bulk-sync').set('Authorization', `Bearer ${apiToken}`).send({ run_id: runId, interactions: [{ fix_key: 'meta-title', status: 'in_progress' }] })
    expect(res.status).toBe(200)
    const fi = db.prepare(`SELECT status FROM fix_interactions WHERE run_id = ? AND fix_key = 'meta-title'`).get(runId) as any
    expect(fi.status).toBe('in_progress')
  })
})
