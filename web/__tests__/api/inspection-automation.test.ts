import { beforeEach, afterEach, it, expect, vi } from 'vitest'
const { db, query } = vi.hoisted(() => ({ db: { from: vi.fn(), rpc: vi.fn() }, query: { select: vi.fn(), eq: vi.fn(), maybeSingle: vi.fn() } }))
vi.mock('@supabase/supabase-js', () => ({ createClient: () => db }))
vi.mock('@/lib/publication-service', () => ({ privatePublicationTexts: vi.fn().mockResolvedValue(['INTERNAL_ONLY_WORDS_MUST_NOT_LEAK_IN_ANY_PUBLIC_REPORT']) }))
import { POST } from '@/app/api/admin/inspections/automation/route'
import { privatePublicationTexts } from '@/lib/publication-service'
const id = 'e133b1af-bd10-4fb6-ae61-558f89c8bd01'
let token: string
function draft() { return { findings: [{ id: 'F1', title: '공개 지적사항', summary: '공개 공시 내용 요약', evidence: [{ page: 1, quote: '공개 공시 내용 근거입니다' }] }],
    matches: [{ finding_id: 'F1', department: '여신부', related_work: '대출 심사', rationale: 'PRIVATE_RATIONALE', evidence: [{ ref: 'private:1', quote: 'PRIVATE_EVIDENCE_VALUE' }], checks: [{ question: '대출 승인 내역을 점검했는가?', evidence_to_request: '승인 내역' }] }], unmatched_finding_ids: [] } }
function job(updates = {}) { return { status: 'needs_review', automation_status: 'pending', result: draft(), review_revision: 3, review_draft: null, versions: { doc: 1 }, ...updates } }
function request(auth = true, body: object = { id }) { return new Request('https://site.test/api/admin/inspections/automation', { method: 'POST', headers: { ...(auth ? { authorization: `Bearer ${token}` } : {}), cookie: 'mp_session=ordinary' }, body: JSON.stringify(body) }) }
beforeEach(() => {
    vi.clearAllMocks(); token = 'fixture-token-'.repeat(4)
    for (const [k,v] of Object.entries({ SANCTION_AUTOMATION_TOKEN: token, SANCTION_AUTOMATION_ENABLED: 'true', SANCTION_PUBLICATIONS_ENABLED: 'true', INTERNAL_DOCUMENTS_ENABLED: 'true', ADMIN_USER_IDS: 'admin', SUPABASE_SERVICE_ROLE_KEY: 'fixture', NEXT_PUBLIC_USE_V2_DB: 'true', NEXT_PUBLIC_SUPABASE_URL_V2: 'https://example.supabase.co' })) vi.stubEnv(k,v)
    db.from.mockReturnValue(query); query.select.mockReturnValue(query); query.eq.mockReturnValue(query)
    query.maybeSingle.mockResolvedValue({ data: job(), error: null }); db.rpc.mockResolvedValue({ error: null })
    vi.mocked(privatePublicationTexts).mockResolvedValue(['INTERNAL_ONLY_WORDS_MUST_NOT_LEAK_IN_ANY_PUBLIC_REPORT'])
})
afterEach(() => vi.unstubAllEnvs())
it('requires the dedicated token, never a dashboard cookie', async () => {
    expect((await POST(request(false))).status).toBe(401)
    token = 'wrong'; expect((await POST(request())).status).toBe(401)
    expect(db.from).not.toHaveBeenCalled()
})
it('honors both feature flags and rejects caller supplied report', async () => {
    expect((await POST(request(true, { id, report: draft() }))).status).toBe(400)
    vi.stubEnv('SANCTION_AUTOMATION_ENABLED', 'false')
    expect((await POST(request())).status).toBe(503)
    expect(db.from).not.toHaveBeenCalled()
})
it('publishes a strict public projection with the checked revision', async () => {
    const response = await POST(request())
    expect(await response.json()).toEqual({ status: 'published' })
    expect(response.headers.get('cache-control')).toContain('no-store')
    const [name, args] = db.rpc.mock.calls[0]
    expect(name).toBe('inspection_auto_publish'); expect(args.p_revision).toBe(3)
    expect(JSON.stringify(args)).not.toMatch(/PRIVATE_|private:1/)
    expect(args.p_report.items[0].related_work).toBe('대출 심사')
})
it.each(['manual', 'published', 'needs_attention', 'none'])('does not overwrite %s states', async state => {
    query.maybeSingle.mockResolvedValue({ data: job({ automation_status: state }), error: null })
    expect(await (await POST(request())).json()).toEqual({ status: 'skipped' })
    expect(db.rpc).not.toHaveBeenCalled()
})
it('does not overwrite an administrator saved draft', async () => {
    query.maybeSingle.mockResolvedValue({ data: job({ review_draft: {} }), error: null })
    expect(await (await POST(request())).json()).toEqual({ status: 'skipped' })
    expect(db.rpc).not.toHaveBeenCalled()
})
it('sends unmatched findings to administrator attention without publication', async () => {
    const result = draft(); result.unmatched_finding_ids = ['F1'] as never[]
    query.maybeSingle.mockResolvedValue({ data: job({ result }), error: null })
    expect(await (await POST(request())).json()).toEqual({ status: 'needs_attention' })
    expect(db.rpc).toHaveBeenCalledWith('inspection_auto_attention', { p_id: id, p_revision: 3 })
})
it('blocks internal original text in the generated related work', async () => {
    const result = draft(); result.matches[0].related_work = 'INTERNAL_ONLY_WORDS_MUST_NOT_LEAK_IN_ANY_PUBLIC_REPORT'
    query.maybeSingle.mockResolvedValue({ data: job({ result }), error: null })
    expect(await (await POST(request())).json()).toEqual({ status: 'needs_attention' })
    expect(db.rpc.mock.calls.some(([name]) => name === 'inspection_auto_publish')).toBe(false)
})
it('sanitizes database conflicts and never retries publishing', async () => {
    db.rpc.mockResolvedValue({ error: { message: 'PRIVATE_CANARY' } })
    const response = await POST(request())
    expect(response.status).toBe(409); expect(await response.text()).not.toContain('PRIVATE_CANARY')
    expect(db.rpc).toHaveBeenCalledTimes(1)
})
