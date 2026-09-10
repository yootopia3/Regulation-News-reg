import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

const { verifyUser, db, query } = vi.hoisted(() => {
    const query = { select: vi.fn(), order: vi.fn(), range: vi.fn() }
    return { verifyUser: vi.fn(), query, db: { auth: { getUser: vi.fn() }, from: vi.fn(), rpc: vi.fn() } }
})
vi.mock('@supabase/supabase-js', () => ({ createClient: () => ({ ...db, auth: { getUser: verifyUser } }) }))
import { GET, POST } from '@/app/api/admin/documents/route'
import { GET as detail, PATCH } from '@/app/api/admin/documents/[id]/route'

beforeEach(() => {
    vi.clearAllMocks()
    vi.stubEnv('INTERNAL_DOCUMENTS_ENABLED', 'true')
    vi.stubEnv('NEXT_PUBLIC_USE_V2_DB', 'true')
    vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL_V2', 'https://example.supabase.co')
    vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY', 'fixture-service-key')
    vi.stubEnv('ADMIN_USER_IDS', 'admin')
    verifyUser.mockResolvedValue({ data: { user: { id: 'admin' } }, error: null })
    db.from.mockReturnValue(query)
    query.select.mockReturnValue(query); query.order.mockReturnValue(query)
    query.range.mockResolvedValue({ data: [], error: null })
})
const request = (method = 'GET', token = 'admin-token', body?: string) => new NextRequest('https://site.test/api/admin/documents', {
    method, headers: { origin: 'https://site.test', cookie: token ? `mp_admin_session=${token}` : 'mp_session=ordinary' }, body,
})

describe('admin document routes', () => {
    it('denies ordinary users on collection and detail endpoints', async () => {
        const context = { params: Promise.resolve({ id: 'e133b1af-bd10-4fb6-ae61-558f89c8bd01' }) }
        expect((await GET(request('GET', ''))).status).toBe(401)
        expect((await POST(request('POST', ''))).status).toBe(401)
        expect((await detail(request('GET', ''), context)).status).toBe(401)
        expect((await PATCH(request('PATCH', '', '{}'), context)).status).toBe(401)
        expect(db.from).not.toHaveBeenCalled(); expect(db.rpc).not.toHaveBeenCalled()
    })
    it('lists only metadata for authorized administrators and disables caching', async () => {
        const response = await GET(request())
        expect(response.status).toBe(200)
        expect(query.select.mock.calls[0][0]).not.toMatch(/object_key|sha256|body|warnings/)
        expect(response.headers.get('cache-control')).toContain('no-store')
    })
    it('rejects arbitrary action data and invalid IDs without mutation', async () => {
        const context = { params: Promise.resolve({ id: 'e133b1af-bd10-4fb6-ae61-558f89c8bd01' }) }
        const response = await PATCH(request('PATCH', 'token', JSON.stringify({ action: 'activate', revision: 0, role: 'admin' })), context)
        expect(response.status).toBe(400); expect(db.rpc).not.toHaveBeenCalled()
    })
    it('passes the verified actor and revision to the transactional service', async () => {
        db.rpc.mockResolvedValue({ data: 4, error: null })
        const id = 'e133b1af-bd10-4fb6-ae61-558f89c8bd01'
        const response = await PATCH(request('PATCH', 'token', JSON.stringify({ action: 'activate', revision: 3 })), { params: Promise.resolve({ id }) })
        expect(response.status).toBe(200)
        expect(db.rpc).toHaveBeenCalledWith('internal_document_action', { p_id: id, p_actor: 'admin', p_input: { action: 'activate', revision: 3 } })
    })
})
