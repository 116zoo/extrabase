import { Router, Request, Response } from 'express'
import bcrypt from 'bcryptjs'
import jwt from 'jsonwebtoken'
import crypto from 'crypto'
import { getDb } from '../db'
import { requireAuth } from '../middleware/auth'
import { sendMagicLink } from '../services/email'
import { JwtPayload } from '../types'

const router = Router()

function signToken(user: any): string {
  const payload: JwtPayload = {
    userId: user.id,
    email: user.email,
    role: user.role,
    clientId: user.client_id
  }
  return jwt.sign(payload, process.env.JWT_SECRET!, { expiresIn: '7d' })
}

// POST /api/auth/login
router.post('/login', (req: Request, res: Response) => {
  const { email, password } = req.body
  if (!email || !password) return res.status(400).json({ error: 'email and password required' })

  const db = getDb()
  const user = db.prepare(`SELECT * FROM users WHERE email = ?`).get(email) as any
  if (!user || !user.password_hash) return res.status(401).json({ error: 'Invalid credentials' })

  if (!bcrypt.compareSync(password, user.password_hash)) {
    return res.status(401).json({ error: 'Invalid credentials' })
  }
  res.json({ token: signToken(user), role: user.role, clientId: user.client_id })
})

// POST /api/auth/magic-request
router.post('/magic-request', (req: Request, res: Response) => {
  const { email } = req.body
  if (!email) return res.status(400).json({ error: 'email required' })

  const db = getDb()
  const user = db.prepare(`SELECT * FROM users WHERE email = ?`).get(email) as any
  if (!user) return res.status(200).json({ ok: true }) // don't leak existence

  const token = crypto.randomBytes(32).toString('hex')
  const expires = new Date(Date.now() + 15 * 60 * 1000).toISOString()
  db.prepare(
    `UPDATE users SET magic_link_token = ?, magic_link_expires_at = ? WHERE id = ?`
  ).run(token, expires, user.id)

  sendMagicLink(user.email, token).catch(console.error)
  res.json({ ok: true })
})

// GET /api/auth/magic-verify?token=xxx
router.get('/magic-verify', (req: Request, res: Response) => {
  const { token } = req.query
  if (!token) return res.status(400).json({ error: 'token required' })

  const db = getDb()
  const user = db.prepare(
    `SELECT * FROM users WHERE magic_link_token = ? AND magic_link_expires_at > datetime('now')`
  ).get(token as string) as any

  if (!user) return res.status(401).json({ error: 'Invalid or expired token' })

  db.prepare(
    `UPDATE users SET magic_link_token = NULL, magic_link_expires_at = NULL WHERE id = ?`
  ).run(user.id)

  res.json({ token: signToken(user), role: user.role, clientId: user.client_id })
})

// PATCH /api/auth/profile (client only — not collaborator)
router.patch('/profile', requireAuth(), (req: Request, res: Response) => {
  if (req.user!.role === 'collaborator') return res.status(403).json({ error: 'Forbidden' })

  const { password } = req.body
  if (!password) return res.status(400).json({ error: 'password required' })

  const hash = bcrypt.hashSync(password, 10)
  getDb().prepare(`UPDATE users SET password_hash = ? WHERE id = ?`).run(hash, req.user!.userId)
  res.json({ ok: true })
})

export default router
