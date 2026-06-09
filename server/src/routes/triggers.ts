import { Router, Request, Response } from 'express'
import { getDb } from '../db'
import { requireAuth } from '../middleware/auth'
import { requireApiToken } from '../middleware/apiToken'

const router = Router()

// POST /api/triggers — superadmin creates a trigger
router.post('/', requireAuth('superadmin'), (req: Request, res: Response) => {
  const { client_id, run_type, notes } = req.body
  if (!client_id || !run_type) return res.status(400).json({ error: 'client_id and run_type required' })
  if (!['full','seo','geo','aeo'].includes(run_type)) return res.status(400).json({ error: 'Invalid run_type' })

  const db = getDb()
  const client = db.prepare(`SELECT id FROM clients WHERE id = ?`).get(client_id)
  if (!client) return res.status(404).json({ error: 'Client not found' })

  const trigger = db.prepare(`
    INSERT INTO run_triggers (client_id, run_type, created_by, notes)
    VALUES (?, ?, ?, ?) RETURNING *
  `).get(client_id, run_type, req.user!.userId, notes || null) as any

  res.status(201).json(trigger)
})

// GET /api/triggers — superadmin lists all triggers
router.get('/', requireAuth('superadmin'), (req: Request, res: Response) => {
  const db = getDb()
  const triggers = db.prepare(`
    SELECT t.*, c.slug, c.name FROM run_triggers t
    JOIN clients c ON t.client_id = c.id
    ORDER BY t.created_at DESC LIMIT 100
  `).all()
  res.json(triggers)
})

// GET /api/triggers/pending — machine poller only (API token)
router.get('/pending', requireApiToken, (req: Request, res: Response) => {
  const db = getDb()
  const triggers = db.prepare(`
    SELECT t.*, c.slug FROM run_triggers t
    JOIN clients c ON t.client_id = c.id
    WHERE t.status = 'pending'
    ORDER BY t.created_at ASC
  `).all()
  res.json(triggers)
})

// PATCH /api/triggers/:id — machine poller updates status (API token)
router.patch('/:id', requireApiToken, (req: Request, res: Response) => {
  const { status } = req.body
  if (!['running','done','failed'].includes(status)) return res.status(400).json({ error: 'Invalid status' })

  const db = getDb()
  const trigger = db.prepare(`SELECT id FROM run_triggers WHERE id = ?`).get(req.params.id)
  if (!trigger) return res.status(404).json({ error: 'Not found' })

  if (status === 'running') {
    db.prepare(`UPDATE run_triggers SET status = ?, picked_up_at = datetime('now') WHERE id = ?`).run(status, req.params.id)
  } else {
    db.prepare(`UPDATE run_triggers SET status = ?, done_at = datetime('now') WHERE id = ?`).run(status, req.params.id)
  }
  res.json({ ok: true })
})

export default router
