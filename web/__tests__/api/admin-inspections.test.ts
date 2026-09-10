import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { NextRequest } from 'next/server'
const { db, query, verify } = vi.hoisted(() => ({ db: { from: vi.fn(), rpc: vi.fn() },
    query: { select: vi.fn(), eq: vi.fn(), in: vi.fn(), order: vi.fn(), limit: vi.fn(), maybeSingle: vi.fn() }, verify: vi.fn() }))
vi.mock('@supabase/supabase-js', () => ({ createClient: () => ({ ...db, auth: { getUser: verify } }) }))
import { GET, POST, PATCH } from '@/app/api/admin/inspections/route'
const id = 'e133b1af-bd10-4fb6-ae61-558f89c8bd01'
function request(method = 'GET', admin = true, body?: object, origin = 'https://site.test', suffix = '') {
    return new NextRequest(`https://site.test/api/admin/inspections${suffix}`, { method, headers: { origin, cookie: admin ? 'mp_admin_session=fixture' : 'mp_session=ordinary' }, body: body ? JSON.stringify(body) : undefined })
}
beforeEach(() => {
    vi.clearAllMocks()
    for (const [key, value] of Object.entries({ INTERNAL_DOCUMENTS_ENABLED: 'true', SANCTION_INSPECTIONS_ENABLED: 'true', NEXT_PUBLIC_USE_V2_DB: 'true', NEXT_PUBLIC_SUPABASE_URL_V2: 'https://example.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'fixture', ADMIN_USER_IDS: 'admin' })) vi.stubEnv(key, value)
    verify.mockResolvedValue({ data: { user: { id: 'admin' } }, error: null })
    db.from.mockReturnValue(query)
    for (const method of ['select', 'eq', 'in', 'order'] as const) query[method].mockReturnValue(query)
    query.limit.mockResolvedValue({ data: [], error: null })
    query.maybeSingle.mockResolvedValue({ data: { id, status: 'needs_review', result: { private_evidence: 'PRIVATE_CANARY' } }, error: null })
    db.rpc.mockResolvedValue({ data: id, error: null })
})
afterEach(() => vi.unstubAllEnvs())
describe('private inspection API', () => {
    it('guards publication actions with admin identity, Origin and explicit confirmation', async () => {
        expect((await PATCH(request('PATCH', false, { action: 'publish', id, revision: 0, reviewed: true }))).status).toBe(401)
        expect((await PATCH(request('PATCH', true, { action: 'withdraw', id, revision: 0 }, 'https://other.test'))).status).toBe(403)
        expect((await PATCH(request('PATCH', true, { action: 'publish', id, revision: 0, reviewed: false }))).status).toBe(400)
        expect(db.rpc).not.toHaveBeenCalled()
    })
    it('denies ordinary sessions including direct draft URLs', async () => {
        expect((await GET(request('GET', false, undefined, undefined, `?id=${id}`))).status).toBe(401)
        expect((await POST(request('POST', false, { article_id: id }))).status).toBe(401)
        expect(db.from).not.toHaveBeenCalled(); expect(db.rpc).not.toHaveBeenCalled()
    })
    it('rejects nonallowlisted users and cross-origin changes', async () => {
        verify.mockResolvedValueOnce({ data: { user: { id: 'other' } }, error: null })
        expect((await GET(request())).status).toBe(403)
        expect((await POST(request('POST', true, { article_id: id }, 'https://other.test'))).status).toBe(403)
        expect(db.rpc).not.toHaveBeenCalled()
    })
    it('returns private drafts only after admin verification and disables caching', async () => {
        const response = await GET(request('GET', true, undefined, undefined, `?id=${id}`))
        expect(response.headers.get('cache-control')).toContain('no-store')
        expect(JSON.stringify(await response.json())).toContain('PRIVATE_CANARY')
    })
    it('rejects caller supplied URL/content and disabled requests', async () => {
        expect((await POST(request('POST', true, { article_id: id, pdf_url: 'https://evil.test' }))).status).toBe(400)
        vi.stubEnv('SANCTION_INSPECTIONS_ENABLED', 'false')
        expect((await POST(request('POST', true, { article_id: id }))).status).toBe(503)
        expect(db.rpc).not.toHaveBeenCalled()
    })
    it('queues only the verified actor and article ID', async () => {
        const response = await POST(request('POST', true, { article_id: id, request_id: id }))
        expect(response.status).toBe(202)
        expect(db.rpc).toHaveBeenCalledWith('inspection_enqueue', { p_article: id, p_actor: 'admin', p_request: id })
    })
})
