import { Router, Request, Response } from 'express'
import { getDb } from '../db'
import { requireAuth } from '../middleware/auth'
import { requireApiToken } from '../middleware/apiToken'

const router = Router()

function parseScore(json: string | null): number | undefined {
  if (!json) return undefined
  try { return JSON.parse(json)?.score } catch { return undefined }
}

// POST /api/runs/upload — watcher only (API token)
router.post('/upload', requireApiToken, (req: Request, res: Response) => {
  const { client_slug, run_date, audit_seo, audit_geo, audit_aeo, audit_schema, audit_llm, fixes, pages_audit, report_md } = req.body
  if (!client_slug || !run_date) return res.status(400).json({ error: 'client_slug and run_date required' })

  const db = getDb()
  const client = db.prepare(`SELECT id FROM clients WHERE slug = ?`).get(client_slug) as any
  if (!client) return res.status(404).json({ error: 'Client not found' })

  const run = db.prepare(`
    INSERT INTO runs (client_id, run_date, audit_seo, audit_geo, audit_aeo, audit_schema, audit_llm, fixes, pages_audit, report_md)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(client_id, run_date) DO UPDATE SET
      audit_seo = excluded.audit_seo,
      audit_geo = excluded.audit_geo,
      audit_aeo = excluded.audit_aeo,
      audit_schema = excluded.audit_schema,
      audit_llm = excluded.audit_llm,
      fixes = excluded.fixes,
      pages_audit = excluded.pages_audit,
      report_md = excluded.report_md
    RETURNING *
  `).get(
    client.id, run_date,
    audit_seo ? JSON.stringify(audit_seo) : null,
    audit_geo ? JSON.stringify(audit_geo) : null,
    audit_aeo ? JSON.stringify(audit_aeo) : null,
    audit_schema ? JSON.stringify(audit_schema) : null,
    audit_llm ? JSON.stringify(audit_llm) : null,
    fixes ? JSON.stringify(fixes) : null,
    pages_audit ? JSON.stringify(pages_audit) : null,
    report_md || null
  ) as any

  res.status(201).json({ id: run.id, run_date: run.run_date, status: run.status })
})

// GET /api/runs — list runs for current client (or all for superadmin)
router.get('/', requireAuth(), (req: Request, res: Response) => {
  const db = getDb()
  const { role, clientId } = req.user!

  let rows: any[]
  if (role === 'superadmin') {
    rows = db.prepare(`
      SELECT r.id, r.run_date, r.status, r.created_at, r.published_at,
             r.client_id, c.slug, c.name,
             r.audit_seo, r.audit_geo, r.audit_aeo, r.audit_schema, r.audit_llm
      FROM runs r JOIN clients c ON r.client_id = c.id
      ORDER BY r.created_at DESC
    `).all()
  } else {
    rows = db.prepare(`
      SELECT id, run_date, status, created_at, published_at,
             audit_seo, audit_geo, audit_aeo, audit_schema, audit_llm
      FROM runs WHERE client_id = ? AND status = 'published'
      ORDER BY run_date DESC
    `).all(clientId)
  }

  const runs = rows.map((r: any) => ({
    ...r,
    score_seo: parseScore(r.audit_seo),
    score_geo: parseScore(r.audit_geo),
    score_aeo: parseScore(r.audit_aeo),
    score_schema: parseScore(r.audit_schema),
    score_llm: parseScore(r.audit_llm),
    audit_seo: undefined,
    audit_geo: undefined,
    audit_aeo: undefined,
    audit_schema: undefined,
    audit_llm: undefined,
  }))

  res.json(runs)
})

// GET /api/runs/:id
router.get('/:id', requireAuth(), (req: Request, res: Response) => {
  const db = getDb()
  const { role, clientId } = req.user!
  const run = db.prepare(`SELECT * FROM runs WHERE id = ?`).get(req.params.id) as any
  if (!run) return res.status(404).json({ error: 'Not found' })
  if (role !== 'superadmin' && (run.client_id !== clientId || run.status !== 'published')) {
    return res.status(403).json({ error: 'Forbidden' })
  }
  // Parse JSON fields
  const jsonFields = ['audit_seo', 'audit_geo', 'audit_aeo', 'audit_schema', 'audit_llm', 'fixes', 'pages_audit']
  for (const f of jsonFields) {
    if (run[f]) run[f] = JSON.parse(run[f])
  }
  res.json(run)
})

// PATCH /api/runs/:id/publish — superadmin only
router.patch('/:id/publish', requireAuth('superadmin'), (req: Request, res: Response) => {
  const { status } = req.body // 'published' | 'pending'
  if (!['published', 'pending'].includes(status)) return res.status(400).json({ error: 'Invalid status' })

  const db = getDb()
  if (status === 'published') {
    db.prepare(`UPDATE runs SET status = 'published', published_at = datetime('now') WHERE id = ?`).run(req.params.id)
  } else {
    db.prepare(`UPDATE runs SET status = 'pending', published_at = NULL WHERE id = ?`).run(req.params.id)
  }
  res.json({ ok: true })
})

export default router
