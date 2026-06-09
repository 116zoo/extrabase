import { Router, Request, Response } from 'express'
import { getDb } from '../db'
import { requireAuth } from '../middleware/auth'
import { requireApiToken } from '../middleware/apiToken'
import { createNotification } from '../services/notify'

const router = Router()

// GET /api/fixes/since?cursor=<ISO>&client=<slug> — local sync pull (API token)
// MUST be registered BEFORE GET /:runId to avoid Express matching 'since' as runId param
router.get('/since', requireApiToken, (req: Request, res: Response) => {
  const { cursor, client } = req.query
  const db = getDb()

  let interactions: any[]
  if (cursor) {
    interactions = db.prepare(`
      SELECT fi.* FROM fix_interactions fi
      JOIN runs r ON fi.run_id = r.id
      JOIN clients c ON r.client_id = c.id
      WHERE fi.updated_at > ? AND c.slug = ?
      ORDER BY fi.updated_at ASC
    `).all(cursor as string, client as string)
  } else {
    interactions = db.prepare(`
      SELECT fi.* FROM fix_interactions fi
      JOIN runs r ON fi.run_id = r.id
      JOIN clients c ON r.client_id = c.id
      WHERE c.slug = ?
      ORDER BY fi.updated_at ASC
    `).all(client as string)
  }
  res.json(interactions)
})

// GET /api/fixes/:runId
router.get('/:runId', requireAuth(), (req: Request, res: Response) => {
  const db = getDb()
  const { role, clientId } = req.user!
  const run = db.prepare(`SELECT * FROM runs WHERE id = ?`).get(req.params.runId) as any
  if (!run) return res.status(404).json({ error: 'Run not found' })
  if (role !== 'superadmin' && run.client_id !== clientId) return res.status(403).json({ error: 'Forbidden' })

  const interactions = db.prepare(
    `SELECT * FROM fix_interactions WHERE run_id = ?`
  ).all(req.params.runId)
  res.json(interactions)
})

// PATCH /api/fixes/:runId/:fixKey
router.patch('/:runId/:fixKey', requireAuth(), (req: Request, res: Response) => {
  const db = getDb()
  const { role, clientId, userId } = req.user!
  const run = db.prepare(`SELECT * FROM runs WHERE id = ?`).get(req.params.runId) as any
  if (!run) return res.status(404).json({ error: 'Run not found' })
  if (role !== 'superadmin' && run.client_id !== clientId) return res.status(403).json({ error: 'Forbidden' })

  const { status, comment } = req.body
  if (status && !['seen','in_progress','done'].includes(status)) {
    return res.status(400).json({ error: 'Invalid status' })
  }

  const existing = db.prepare(
    `SELECT id FROM fix_interactions WHERE run_id = ? AND fix_key = ?`
  ).get(req.params.runId, req.params.fixKey)

  if (existing) {
    db.prepare(`
      UPDATE fix_interactions SET
        status = COALESCE(?, status),
        comment = COALESCE(?, comment),
        updated_at = datetime('now')
      WHERE run_id = ? AND fix_key = ?
    `).run(status || null, comment !== undefined ? comment : null, req.params.runId, req.params.fixKey)
  } else {
    db.prepare(`
      INSERT INTO fix_interactions (run_id, fix_key, user_id, status, comment)
      VALUES (?, ?, ?, ?, ?)
    `).run(req.params.runId, req.params.fixKey, userId, status || 'seen', comment || null)
  }

  // Notify superadmin if interaction comes from client/collaborator
  if (role !== 'superadmin') {
    const admins = db.prepare(`SELECT id FROM users WHERE role = 'superadmin'`).all() as any[]
    admins.forEach(a => createNotification(db, a.id, 'fix_updated', run.client_id, run.id, req.params.fixKey))
  }

  res.json({ ok: true })
})

// POST /api/fixes/bulk-sync — watcher only (API token), push local fixes to central
router.post('/bulk-sync', requireApiToken, (req: Request, res: Response) => {
  const { run_id, interactions } = req.body
  if (!run_id || !Array.isArray(interactions)) return res.status(400).json({ error: 'run_id and interactions[] required' })

  const db = getDb()
  const upsert = db.prepare(`
    INSERT INTO fix_interactions (run_id, fix_key, user_id, status, comment, synced_at)
    VALUES (@run_id, @fix_key, @user_id, @status, @comment, datetime('now'))
    ON CONFLICT(run_id, fix_key) DO UPDATE SET
      status = excluded.status,
      comment = excluded.comment,
      synced_at = datetime('now')
  `)
  const insertMany = db.transaction((items: any[]) => {
    for (const item of items) {
      upsert.run({ run_id, fix_key: item.fix_key, user_id: 1, status: item.status || 'seen', comment: item.comment || null })
    }
  })
  insertMany(interactions)
  res.json({ ok: true, count: interactions.length })
})

export default router
