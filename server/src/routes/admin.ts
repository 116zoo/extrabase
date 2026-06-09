import { Router, Request, Response } from 'express'
import bcrypt from 'bcryptjs'
import crypto from 'crypto'
import jwt from 'jsonwebtoken'
import { getDb } from '../db'
import { requireAuth } from '../middleware/auth'
import { sendMagicLink } from '../services/email'
import { JwtPayload } from '../types'

const router = Router()
const auth = requireAuth('superadmin')

// GET /api/admin/clients
router.get('/clients', auth, (req: Request, res: Response) => {
  const clients = getDb().prepare(`SELECT * FROM clients ORDER BY name`).all()
  res.json(clients)
})

// POST /api/admin/clients
router.post('/clients', auth, (req: Request, res: Response) => {
  const { slug, name, site_url, sector, notify_email } = req.body
  if (!slug || !name || !site_url) return res.status(400).json({ error: 'slug, name, site_url required' })

  const db = getDb()
  // Insert first to get the id, then generate token with clientId
  const tempClient = db.prepare(`
    INSERT INTO clients (slug, name, site_url, sector, notify_email)
    VALUES (?, ?, ?, ?, ?) RETURNING *
  `).get(slug, name, site_url, sector || null, notify_email || null) as any

  const staticToken = jwt.sign(
    { userId: 0, email: '', role: 'client' as const, clientId: tempClient.id } as JwtPayload,
    process.env.JWT_SECRET!,
    { expiresIn: '365d' }
  )
  db.prepare(`UPDATE clients SET client_static_token = ? WHERE id = ?`).run(staticToken, tempClient.id)

  res.status(201).json({ ...tempClient, client_static_token: staticToken })
})

// GET /api/admin/clients/:id
router.get('/clients/:id', auth, (req: Request, res: Response) => {
  const client = getDb().prepare(`SELECT * FROM clients WHERE id = ?`).get(req.params.id)
  if (!client) return res.status(404).json({ error: 'Not found' })
  res.json(client)
})

// PUT /api/admin/clients/:id
router.put('/clients/:id', auth, (req: Request, res: Response) => {
  const { name, site_url, sector, notify_email } = req.body
  getDb().prepare(`UPDATE clients SET name = COALESCE(?, name), site_url = COALESCE(?, site_url), sector = COALESCE(?, sector), notify_email = COALESCE(?, notify_email) WHERE id = ?`)
    .run(name || null, site_url || null, sector || null, notify_email || null, req.params.id)
  res.json({ ok: true })
})

// DELETE /api/admin/clients/:id
router.delete('/clients/:id', auth, (req: Request, res: Response) => {
  getDb().prepare(`DELETE FROM clients WHERE id = ?`).run(req.params.id)
  res.json({ ok: true })
})

// GET /api/admin/users?client_id=N
router.get('/users', auth, (req: Request, res: Response) => {
  const db = getDb()
  const users = req.query.client_id
    ? db.prepare(`SELECT id, email, role, client_id, created_at FROM users WHERE client_id = ?`).all(req.query.client_id)
    : db.prepare(`SELECT id, email, role, client_id, created_at FROM users`).all()
  res.json(users)
})

// POST /api/admin/users — create user + send magic link invite
router.post('/users', auth, (req: Request, res: Response) => {
  const { email, role, client_id } = req.body
  if (!email || !role) return res.status(400).json({ error: 'email and role required' })
  if (!['client','collaborator','superadmin'].includes(role)) return res.status(400).json({ error: 'Invalid role' })

  const db = getDb()
  const token = crypto.randomBytes(32).toString('hex')
  const expires = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString() // 24h for invite
  const user = db.prepare(`
    INSERT INTO users (email, role, client_id, magic_link_token, magic_link_expires_at)
    VALUES (?, ?, ?, ?, ?) RETURNING id, email, role, client_id
  `).get(email, role, client_id || null, token, expires) as any

  sendMagicLink(email, token).catch(console.error)
  res.status(201).json(user)
})

// DELETE /api/admin/users/:id
router.delete('/users/:id', auth, (req: Request, res: Response) => {
  getDb().prepare(`DELETE FROM users WHERE id = ?`).run(req.params.id)
  res.json({ ok: true })
})

// POST /api/admin/clients/:id/users — create user for a specific client + send magic link invite
router.post('/clients/:id/users', auth, (req: Request, res: Response) => {
  const { email, role } = req.body
  const clientId = parseInt(req.params.id, 10)
  if (!email || !role) return res.status(400).json({ error: 'email and role required' })
  if (!['client','collaborator','superadmin'].includes(role)) return res.status(400).json({ error: 'Invalid role' })

  const db = getDb()
  const token = crypto.randomBytes(32).toString('hex')
  const expires = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString() // 24h for invite
  const user = db.prepare(`
    INSERT INTO users (email, role, client_id, magic_link_token, magic_link_expires_at)
    VALUES (?, ?, ?, ?, ?) RETURNING id, email, role, client_id
  `).get(email, role, clientId, token, expires) as any

  sendMagicLink(email, token).catch(console.error)
  res.status(201).json(user)
})

// GET /api/admin/notifications?unread=true
router.get('/notifications', auth, (req: Request, res: Response) => {
  const db = getDb()
  const query = req.query.unread === 'true'
    ? `SELECT * FROM notifications WHERE read_at IS NULL ORDER BY created_at DESC LIMIT 50`
    : `SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100`
  const notifs = db.prepare(query).all()
  res.json(notifs)
})

// PATCH /api/admin/notifications/:id/read
router.patch('/notifications/:id/read', auth, (req: Request, res: Response) => {
  getDb().prepare(`UPDATE notifications SET read_at = datetime('now') WHERE id = ?`).run(req.params.id)
  res.json({ ok: true })
})

// GET /api/admin/tokens
router.get('/tokens', auth, (req: Request, res: Response) => {
  const tokens = getDb().prepare(`SELECT id, label, created_at, last_used_at FROM api_tokens`).all()
  res.json(tokens)
})

// POST /api/admin/tokens — create new API token, return raw once
router.post('/tokens', auth, (req: Request, res: Response) => {
  const { label } = req.body
  if (!label) return res.status(400).json({ error: 'label required' })
  const raw = crypto.randomBytes(32).toString('hex')
  const hash = crypto.createHash('sha256').update(raw).digest('hex')
  getDb().prepare(`INSERT INTO api_tokens (label, token_hash) VALUES (?, ?)`).run(label, hash)
  res.status(201).json({ label, token: raw }) // raw shown once only
})

// DELETE /api/admin/tokens/:id
router.delete('/tokens/:id', auth, (req: Request, res: Response) => {
  getDb().prepare(`DELETE FROM api_tokens WHERE id = ?`).run(req.params.id)
  res.json({ ok: true })
})

export default router
