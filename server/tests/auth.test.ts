import { createTestDb, createClient, createUser } from './helpers'

describe('migrate()', () => {
  it('creates all tables without error', () => {
    const db = createTestDb()
    const tables = db.prepare(
      `SELECT name FROM sqlite_master WHERE type='table' ORDER BY name`
    ).all().map((r: any) => r.name)
    expect(tables).toEqual(expect.arrayContaining([
      'api_tokens', 'clients', 'fix_interactions',
      'local_sync_cursors', 'notifications', 'run_triggers',
      'runs', 'users'
    ]))
  })

  it('createClient() inserts and returns a client', () => {
    const db = createTestDb()
    const client = createClient(db)
    expect(client.slug).toBe('test-client')
  })
})
