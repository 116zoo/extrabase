import request from 'supertest'
import express from 'express'
import { createTestDb, createClient, createUser, getToken, createApiToken, TEST_JWT_SECRET } from './helpers'
import triggersRouter from '../src/routes/triggers'

process.env.JWT_SECRET = TEST_JWT_SECRET

function buildApp() {
  const app = express()
  app.use(express.json())
  app.use('/api/triggers', triggersRouter)
  return app
}

describe('POST /api/triggers', () => {
  let db: any, admin: any, client: any, clientUser: any, app: any

  beforeEach(() => {
    db = createTestDb()
    client = createClient(db)
    admin = createUser(db, 'admin@test.com', 'superadmin')
    clientUser = createUser(db, 'client@test.com', 'client', client.id)
    app = buildApp()
  })

  it('superadmin can create a trigger', async () => {
    const res = await request(app)
      .post('/api/triggers')
      .set('Authorization', `Bearer ${getToken(admin)}`)
      .send({ client_id: client.id, run_type: 'full' })
    expect(res.status).toBe(201)
    expect(res.body.status).toBe('pending')
    expect(res.body.run_type).toBe('full')
  })

  it('client cannot create a trigger', async () => {
    const res = await request(app)
      .post('/api/triggers')
      .set('Authorization', `Bearer ${getToken(clientUser)}`)
      .send({ client_id: client.id, run_type: 'full' })
    expect(res.status).toBe(403)
  })
})

describe('GET /api/triggers/pending + PATCH', () => {
  let db: any, admin: any, client: any, apiToken: string, app: any

  beforeEach(() => {
    db = createTestDb()
    client = createClient(db)
    admin = createUser(db, 'admin@test.com', 'superadmin')
    apiToken = createApiToken(db)
    app = buildApp()
    db.prepare(`INSERT INTO run_triggers (client_id, run_type, created_by) VALUES (?, 'full', ?)`).run(client.id, admin.id)
  })

  it('poller retrieves pending triggers via API token', async () => {
    const res = await request(app)
      .get('/api/triggers/pending')
      .set('Authorization', `Bearer ${apiToken}`)
    expect(res.status).toBe(200)
    expect(res.body).toHaveLength(1)
    expect(res.body[0].slug).toBe('test-client')
  })

  it('poller marks trigger as running then done', async () => {
    const pending = await request(app).get('/api/triggers/pending').set('Authorization', `Bearer ${apiToken}`)
    const id = pending.body[0].id

    await request(app).patch(`/api/triggers/${id}`).set('Authorization', `Bearer ${apiToken}`).send({ status: 'running' })
    const running = db.prepare(`SELECT status, picked_up_at FROM run_triggers WHERE id = ?`).get(id) as any
    expect(running.status).toBe('running')
    expect(running.picked_up_at).not.toBeNull()

    await request(app).patch(`/api/triggers/${id}`).set('Authorization', `Bearer ${apiToken}`).send({ status: 'done' })
    const done = db.prepare(`SELECT status, done_at FROM run_triggers WHERE id = ?`).get(id) as any
    expect(done.status).toBe('done')
    expect(done.done_at).not.toBeNull()

    const pendingAfter = await request(app).get('/api/triggers/pending').set('Authorization', `Bearer ${apiToken}`)
    expect(pendingAfter.body).toHaveLength(0)
  })
})
