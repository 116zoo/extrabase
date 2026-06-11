import express from 'express'
import path from 'path'
import rateLimit from 'express-rate-limit'
import { getDb, migrate } from './db'
import authRouter from './routes/auth'
import runsRouter from './routes/runs'
import fixesRouter from './routes/fixes'
import triggersRouter from './routes/triggers'
import adminRouter from './routes/admin'

const app = express()

// Parse JSON
app.use(express.json({ limit: '50mb' }))

// Dynamic CORS from clients table — only for API routes
app.use('/api', (req, res, next) => {
  const db = getDb()
  const clients = db.prepare(`SELECT site_url FROM clients`).all() as any[]
  const allowed = new Set([
    process.env.ADMIN_URL || 'http://localhost:3000',
    ...clients.map(c => c.site_url)
  ])
  const origin = req.headers.origin
  if (origin && allowed.has(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin)
    res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PATCH,DELETE,OPTIONS')
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization')
  }
  if (req.method === 'OPTIONS') return res.sendStatus(204)
  next()
})

// Rate limit on auth
const authLimiter = rateLimit({ windowMs: 60_000, max: 10, standardHeaders: true, legacyHeaders: false })
app.use('/api/auth', authLimiter)

// Routes
app.use('/api/auth', authRouter)
app.use('/api/runs', runsRouter)
app.use('/api/fixes', fixesRouter)
app.use('/api/triggers', triggersRouter)
app.use('/api/admin', adminRouter)

// API 404 handler — prevents SPA wildcard from catching unmatched /api/* routes
app.use('/api', (req, res) => {
  res.status(404).json({ error: 'Not found' })
})

// Serve React SPA for all non-API routes
const publicDir = path.join(__dirname, '../public')
app.use(express.static(publicDir))
app.get('*', (req, res) => {
  res.sendFile(path.join(publicDir, 'index.html'))
})

// Init DB and start
const db = getDb()
migrate(db)

const PORT = Number(process.env.PORT) || 3000
app.listen(PORT, () => console.log(`SEO Dashboard API running on port ${PORT}`))

export default app
