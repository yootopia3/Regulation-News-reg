import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
const { db, query, verify } = vi.hoisted(() => ({ db: { from: vi.fn(), rpc: vi.fn() }, query: { select: vi.fn(), eq: vi.fn(), order: vi.fn(), range: vi.fn() }, verify: vi.fn() }))
vi.mock('@/lib/auth', () => ({ verifySession: verify }))
vi.mock('@/lib/admin-auth', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/admin-auth')>(), adminClient: () => db }))
import { GET } from '@/app/api/sanction-publications/route'
const id = 'e133b1af-bd10-4fb6-ae61-558f89c8bd01'
const report = { items: [{ finding_id: 'F1', title: '공개 지적', summary: '공개 요약', departments: ['확인부'], related_work: '관련 업무', source_pages: [1], checks: [{ question: '업무를 확인했는가?', evidence_to_request: '확인 자료' }] }] }
const request = (query = '') => new NextRequest(`https://site.test/api/sanction-publications${query}`, { headers: { cookie: 'mp_session=fixture' } })
beforeEach(() => {
    vi.clearAllMocks(); vi.stubEnv('SANCTION_PUBLICATIONS_ENABLED', 'true')
    verify.mockResolvedValue({ exp: 9999999999 })
    db.from.mockReturnValue(query)
    db.rpc.mockResolvedValue({ data: null, error: null })
    query.select.mockReturnValue(query); query.eq.mockReturnValue(query); query.order.mockReturnValue(query)
    query.range.mockResolvedValue({ data: [{ inspection_id: id, article_id: id, published_at: '2026-09-10', report, articles: { title: '합성 은행 공시', link: 'https://www.fss.or.kr/fss/notice', published_at: '2026-09-09' }, internal_extra: 'PRIVATE_CANARY' }], error: null })
})
afterEach(() => vi.unstubAllEnvs())
describe('published-only public API', () => {
    it('resolves identical public notices and preserves the requested card identity', async () => {
        query.range.mockResolvedValueOnce({ data: [], error: null })
        db.rpc.mockResolvedValue({ data: id, error: null })
        const alias = 'e133b1af-bd10-4fb6-ae61-558f89c8bd02'
        const res = await GET(request(`?articleId=${alias}`))
        expect(res.status).toBe(200)
        expect(db.rpc).toHaveBeenCalledWith('inspection_publication_alias', { p_article: alias })
        expect((await res.json()).reports[0].article_id).toBe(alias)
    })
    it('looks up an exact article server-side and rejects invalid article IDs', async () => {
        const res = await GET(request(`?articleId=${id}&offset=100`))
        expect(res.status).toBe(200)
        expect(query.eq).toHaveBeenCalledWith('article_id', id)
        expect(query.range).toHaveBeenCalledWith(0, 19)
        expect((await res.json()).nextOffset).toBeNull()
        expect((await GET(request('?articleId=not-a-uuid'))).status).toBe(400)
    })
    it('requires a valid dashboard session for JSON and direct Excel URLs', async () => {
        verify.mockResolvedValue(null)
        expect((await GET(request())).status).toBe(401)
        expect((await GET(request(`?id=${id}&format=xlsx`))).status).toBe(401)
        expect(db.from).not.toHaveBeenCalled()
    })
    it('selects published snapshots only and never returns private data or cacheable responses', async () => {
        const res = await GET(request())
        expect(res.status).toBe(200)
        expect(res.headers.get('cache-control')).toContain('no-store')
        expect(query.eq).toHaveBeenCalledWith('status', 'published')
        expect(await res.text()).not.toContain('PRIVATE_CANARY')
        expect(db.from).toHaveBeenCalledWith('sanction_publications')
    })
    it('refuses malformed snapshots without echoing raw data', async () => {
        query.range.mockResolvedValue({ data: [{ inspection_id: id, report: { ...report, quote: 'PRIVATE_CANARY' } }], error: null })
        const res = await GET(request())
        expect(res.status).toBe(503); expect(await res.text()).not.toContain('PRIVATE_CANARY')
    })
    it('returns no withdrawn/deleted export and respects feature off', async () => {
        query.range.mockResolvedValue({ data: [], error: null })
        expect((await GET(request(`?id=${id}&format=xlsx`))).status).toBe(404)
        vi.stubEnv('SANCTION_PUBLICATIONS_ENABLED', 'false')
        expect((await GET(request(`?id=${id}&format=xlsx`))).status).toBe(404)
    })
    it('exports an approved snapshot with a fixed safe filename', async () => {
        const res = await GET(request(`?id=${id}&format=xlsx`))
        expect(res.status).toBe(200)
        expect(res.headers.get('content-disposition')).toContain('sanction-inspection.xlsx')
        expect((await res.arrayBuffer()).byteLength).toBeGreaterThan(1000)
    })
})
