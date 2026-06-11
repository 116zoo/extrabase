import request from 'supertest'
import express from 'express'
import { createTestDb, createClient, createUser, getToken, createApiToken, TEST_JWT_SECRET } from './helpers'
import runsRouter from '../src/routes/runs'

process.env.JWT_SECRET = TEST_JWT_SECRET

function buildApp() {
  const app = express()
  app.use(express.json())
  app.use('/api/runs', runsRouter)
  return app
}

describe('POST /api/runs/upload', () => {
  let db: any, apiToken: string, app: any

  beforeEach(() => {
    db = createTestDb()
    createClient(db, 'crystal-metamorphose-fr')
    apiToken = createApiToken(db)
    app = buildApp()
  })

  it('returns 401 without API token', async () => {
    const res = await request(app).post('/api/runs/upload').send({})
    expect(res.status).toBe(401)
  })

  it('uploads a run and returns 201', async () => {
    const res = await request(app)
      .post('/api/runs/upload')
      .set('Authorization', `Bearer ${apiToken}`)
      .send({ client_slug: 'crystal-metamorphose-fr', run_date: '2026-06-10', audit_seo: { score: 80 } })
    expect(res.status).toBe(201)
    expect(res.body.run_date).toBe('2026-06-10')
    expect(res.body.status).toBe('pending')
  })

  it('is idempotent on duplicate run_date (upsert)', async () => {
    const payload = { client_slug: 'crystal-metamorphose-fr', run_date: '2026-06-10', audit_seo: { score: 80 } }
    await request(app).post('/api/runs/upload').set('Authorization', `Bearer ${apiToken}`).send(payload)
    const res = await request(app).post('/api/runs/upload').set('Authorization', `Bearer ${apiToken}`).send({ ...payload, audit_seo: { score: 90 } })
    expect(res.status).toBe(201)
    const run = db.prepare(`SELECT audit_seo FROM runs WHERE run_date = '2026-06-10'`).get() as any
    expect(JSON.parse(run.audit_seo).score).toBe(90)
  })
})

describe('GET /api/runs', () => {
  let db: any, admin: any, client: any, clientUser: any, app: any

  beforeEach(() => {
    db = createTestDb()
    client = createClient(db, 'crystal-metamorphose-fr')
    admin = createUser(db, 'admin@test.com', 'superadmin')
    clientUser = createUser(db, 'client@test.com', 'client', client.id)
    app = buildApp()
    db.prepare(`INSERT INTO runs (client_id, run_date, status, published_at) VALUES (?, '2026-06-10', 'published', datetime('now'))`).run(client.id)
    db.prepare(`INSERT INTO runs (client_id, run_date, status) VALUES (?, '2026-06-09', 'pending')`).run(client.id)
  })

  it('client sees only published runs', async () => {
    const res = await request(app)
      .get('/api/runs')
      .set('Authorization', `Bearer ${getToken(clientUser)}`)
    expect(res.status).toBe(200)
    expect(res.body).toHaveLength(1)
    expect(res.body[0].run_date).toBe('2026-06-10')
  })

  it('superadmin sees all runs', async () => {
    const res = await request(app)
      .get('/api/runs')
      .set('Authorization', `Bearer ${getToken(admin)}`)
    expect(res.status).toBe(200)
    expect(res.body).toHaveLength(2)
  })
})

describe('PATCH /api/runs/:id/publish', () => {
  let db: any, admin: any, clientUser: any, runId: number, app: any

  beforeEach(() => {
    db = createTestDb()
    const client = createClient(db)
    admin = createUser(db, 'admin@test.com', 'superadmin')
    clientUser = createUser(db, 'client@test.com', 'client', client.id)
    app = buildApp()
    const run = db.prepare(`INSERT INTO runs (client_id, run_date) VALUES (?, '2026-06-10') RETURNING id`).get(client.id) as any
    runId = run.id
  })

  it('superadmin can publish a run', async () => {
    const res = await request(app)
      .patch(`/api/runs/${runId}/publish`)
      .set('Authorization', `Bearer ${getToken(admin)}`)
      .send({ status: 'published' })
    expect(res.status).toBe(200)
    const run = db.prepare(`SELECT status FROM runs WHERE id = ?`).get(runId) as any
    expect(run.status).toBe('published')
  })

  it('client cannot publish a run', async () => {
    const res = await request(app)
      .patch(`/api/runs/${runId}/publish`)
      .set('Authorization', `Bearer ${getToken(clientUser)}`)
      .send({ status: 'published' })
    expect(res.status).toBe(403)
  })
})

describe('POST /api/runs/upload — audit_schema + audit_llm', () => {
  let db: any, apiToken: string, app: any

  beforeEach(() => {
    db = createTestDb()
    createClient(db, 'crystal-metamorphose-fr')
    apiToken = createApiToken(db)
    app = buildApp()
  })

  it('uploads a run with audit_schema and audit_llm', async () => {
    const res = await request(app)
      .post('/api/runs/upload')
      .set('Authorization', `Bearer ${apiToken}`)
      .send({
        client_slug: 'crystal-metamorphose-fr',
        run_date: '2026-06-11',
        audit_seo: { score: 80 },
        audit_schema: { score: 85 },
        audit_llm: { score: 72 }
      })
    expect(res.status).toBe(201)
    const run = db.prepare(`SELECT audit_schema, audit_llm FROM runs WHERE run_date = '2026-06-11'`).get() as any
    expect(JSON.parse(run.audit_schema).score).toBe(85)
    expect(JSON.parse(run.audit_llm).score).toBe(72)
  })
})

describe('GET /api/runs — score fields in list', () => {
  let db: any, admin: any, clientUser: any, client: any, app: any

  beforeEach(() => {
    db = createTestDb()
    client = createClient(db, 'crystal-metamorphose-fr')
    admin = createUser(db, 'admin@test.com', 'superadmin')
    clientUser = createUser(db, 'client@test.com', 'client', client.id)
    app = buildApp()
    db.prepare(`
      INSERT INTO runs (client_id, run_date, status, published_at, audit_seo, audit_geo, audit_aeo, audit_schema, audit_llm)
      VALUES (?, '2026-06-11', 'published', datetime('now'), ?, ?, ?, ?, ?)
    `).run(
      client.id,
      JSON.stringify({ score: 80 }),
      JSON.stringify({ score: 65 }),
      JSON.stringify({ score: 72 }),
      JSON.stringify({ score: 85 }),
      JSON.stringify({ score: 70 })
    )
  })

  it('returns score fields in list response', async () => {
    const res = await request(app)
      .get('/api/runs')
      .set('Authorization', `Bearer ${getToken(clientUser)}`)
    expect(res.status).toBe(200)
    expect(res.body[0].score_seo).toBe(80)
    expect(res.body[0].score_geo).toBe(65)
    expect(res.body[0].score_aeo).toBe(72)
    expect(res.body[0].score_schema).toBe(85)
    expect(res.body[0].score_llm).toBe(70)
  })

  it('does not include raw audit JSON in list response', async () => {
    const res = await request(app)
      .get('/api/runs')
      .set('Authorization', `Bearer ${getToken(clientUser)}`)
    expect(res.body[0].audit_seo).toBeUndefined()
    expect(res.body[0].audit_schema).toBeUndefined()
  })
})
