import { Request, Response, NextFunction } from 'express'
import jwt from 'jsonwebtoken'
import { JwtPayload, Role } from '../types'

export function requireAuth(role?: Role) {
  return (req: Request, res: Response, next: NextFunction) => {
    const header = req.headers.authorization
    if (!header?.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'Missing token' })
    }
    const token = header.slice(7)
    try {
      const payload = jwt.verify(token, process.env.JWT_SECRET!) as JwtPayload
      req.user = payload
      if (role && payload.role !== role) {
        return res.status(403).json({ error: 'Forbidden' })
      }
      next()
    } catch {
      return res.status(401).json({ error: 'Invalid token' })
    }
  }
}
