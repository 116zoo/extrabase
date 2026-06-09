export type Role = 'superadmin' | 'client' | 'collaborator'
export type RunStatus = 'pending' | 'published'
export type FixStatus = 'seen' | 'in_progress' | 'done'
export type TriggerStatus = 'pending' | 'running' | 'done' | 'failed'
export type RunType = 'full' | 'seo' | 'geo' | 'aeo'

export interface JwtPayload {
  userId: number
  email: string
  role: Role
  clientId: number | null
}

export interface AuthRequest extends Express.Request {
  user: JwtPayload
}

declare global {
  namespace Express {
    interface Request {
      user?: JwtPayload
    }
  }
}
