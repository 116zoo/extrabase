import { Request, Response, NextFunction } from 'express'
import crypto from 'crypto'
import { getDb } from '../db'

export function requireApiToken(req: Request, res: Response, next: NextFunction) {
  const header = req.headers.authorization
  if (!header?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing token' })
  }
  const raw = header.slice(7)
  const hash = crypto.createHash('sha256').update(raw).digest('hex')
  const db = getDb()
  const token = db.prepare(
    `SELECT id FROM api_tokens WHERE token_hash = ?`
  ).get(hash)
  if (!token) {
    return res.status(401).json({ error: 'Invalid API token' })
  }
  db.prepare(`UPDATE api_tokens SET last_used_at = datetime('now') WHERE token_hash = ?`).run(hash)
  next()
}
