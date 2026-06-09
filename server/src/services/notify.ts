import Database from 'better-sqlite3'

export function createNotification(
  db: Database.Database,
  userId: number,
  type: string,
  clientId: number,
  runId: number,
  fixKey: string
): void {
  db.prepare(`
    INSERT INTO notifications (user_id, type, client_id, run_id, fix_key)
    VALUES (?, ?, ?, ?, ?)
  `).run(userId, type, clientId, runId, fixKey)
}
