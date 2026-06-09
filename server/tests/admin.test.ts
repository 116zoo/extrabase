import request from 'supertest'
import express from 'express'
import { createTestDb, createClient, createUser, getToken, TEST_JWT_SECRET } from './helpers'
import adminRouter from '../src/routes/admin'

process.env.JWT_SECRET = TEST_JWT_SECRET

// Mock email service
jest.mock('../src/services/email', () => ({
  sendMagicLink: jest.fn().mockResolvedValue(undefined)
}))

function buildApp() {
  const app = express()
  app.use(express.json())
  app.use('/api/admin', adminRouter)
  return app
}

describe('Admin routes', () => {
  let db: any, admin: any, clientUser: any, client: any, app: any

  beforeEach(() => {
    db = createTestDb()
    client = createClient(db)
    admin = createUser(db, 'admin@test.com', 'superadmin')
    clientUser = createUser(db, 'client@test.com', 'client', client.id)
    app = buildApp()
  })

  it('GET /api/admin/clients requires superadmin', async () => {
    const res = await request(app).get('/api/admin/clients').set('Authorization', `Bearer ${getToken(clientUser)}`)
    expect(res.status).toBe(403)
  })

  it('GET /api/admin/clients returns all clients', async () => {
    const res = await request(app).get('/api/admin/clients').set('Authorization', `Bearer ${getToken(admin)}`)
    expect(res.status).toBe(200)
    expect(res.body).toHaveLength(1)
    expect(res.body[0].slug).toBe('test-client')
  })

  it('POST /api/admin/clients creates client with static token containing clientId', async () => {
    const res = await request(app)
      .post('/api/admin/clients')
      .set('Authorization', `Bearer ${getToken(admin)}`)
      .send({ slug: 'new-client', name: 'New Client', site_url: 'https://new.com' })
    expect(res.status).toBe(201)
    expect(res.body.client_static_token).toBeDefined()
    // Verify clientId is embedded in the token
    const payload = JSON.parse(Buffer.from(res.body.client_static_token.split('.')[1], 'base64').toString())
    expect(payload.clientId).toBe(res.body.id)
  })

  it('GET /api/admin/clients/:id returns single client', async () => {
    const res = await request(app)
      .get(`/api/admin/clients/${client.id}`)
      .set('Authorization', `Bearer ${getToken(admin)}`)
    expect(res.status).toBe(200)
    expect(res.body.id).toBe(client.id)
    expect(res.body.slug).toBe('test-client')
  })

  it('GET /api/admin/clients/:id returns 404 for unknown id', async () => {
    const res = await request(app)
      .get('/api/admin/clients/99999')
      .set('Authorization', `Bearer ${getToken(admin)}`)
    expect(res.status).toBe(404)
  })

  it('POST /api/admin/users creates user and sends magic link', async () => {
    const { sendMagicLink } = require('../src/services/email')
    const res = await request(app)
      .post('/api/admin/users')
      .set('Authorization', `Bearer ${getToken(admin)}`)
      .send({ email: 'collab@test.com', role: 'collaborator', client_id: client.id })
    expect(res.status).toBe(201)
    expect(sendMagicLink).toHaveBeenCalledWith('collab@test.com', expect.any(String))
  })

  it('POST /api/admin/tokens returns raw token once', async () => {
    const res = await request(app)
      .post('/api/admin/tokens')
      .set('Authorization', `Bearer ${getToken(admin)}`)
      .send({ label: 'watcher-prod' })
    expect(res.status).toBe(201)
    expect(res.body.token).toMatch(/^[a-f0-9]{64}$/)
    // Raw not stored — only hash in DB
    const token = db.prepare(`SELECT token_hash FROM api_tokens WHERE label = 'watcher-prod'`).get() as any
    expect(token.token_hash).not.toBe(res.body.token)
  })
})
