// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
const mocks = vi.hoisted(() => ({ createClient: vi.fn() }))
vi.mock('@supabase/supabase-js', () => ({ createClient: mocks.createClient }))
import { signSession } from '@/lib/auth'
import { GET as list, POST as create } from '@/app/api/board/[id]/comments/route'
import { PATCH as update, DELETE as remove } from '@/app/api/board/[id]/comments/[commentId]/route'
import { verifyBoardPassword } from '@/lib/board/password'

type Row = Record<string, unknown>
const postId = '00000000-0000-4000-8000-000000000001'
const otherPost = '00000000-0000-4000-8000-000000000002'
const password = 'test-comment-password'
const input = { author_name: '담당자', body: '검토 의견입니다.', password }
let posts: Row[], comments: Row[], session: string
let conflict: boolean, denyRate: boolean, insertError: string | null, deleteError: string | null, unpublishOnList: boolean
let db: ReturnType<typeof fakeDb>
function fakeDb() {
    return {
        auth: { getUser: vi.fn().mockResolvedValue({ data: { user: { id: 'board-admin' } }, error: null }) },
        rpc: vi.fn(async (name: string, args: { p_limit: number }) => { void name; void args; return { data: !denyRate, error: null } }),
        from: vi.fn((table: string) => {
            let columns = '', mode = 'read', single = false, values: Row = {}, start = 0, end = 999
            const filters: Array<[string, unknown]> = []
            const orders: Array<[string, boolean]> = []
            const query = {
                select: (value: string) => { columns = value; return query },
                eq: (key: string, value: unknown) => { filters.push([key, value]); return query },
                order: (key: string, options: { ascending: boolean }) => { orders.push([key, options.ascending]); return query },
                range: (a: number, b: number) => { start = a; end = b; return query },
                maybeSingle: () => { single = true; return query }, single: () => { single = true; return query },
                insert: (value: Row) => { values = value; mode = 'insert'; return query },
                update: (value: Row) => { values = value; mode = 'update'; return query }, delete: () => { mode = 'delete'; return query },
                then: (resolve: (value: unknown) => unknown) => {
                    if (table === 'board_comments' && mode === 'insert' && insertError) return Promise.resolve(resolve({ data: null, error: { code: insertError } }))
                    if (table === 'board_comments' && mode === 'delete' && deleteError) return Promise.resolve(resolve({ data: null, error: { code: deleteError } }))
                    if (table === 'board_comments' && mode === 'read' && unpublishOnList) posts[0].status = 'draft'
                    let selected = (table === 'board_posts' ? posts : comments).filter(row => filters.every(([key, value]) => key === 'board_posts.status'
                        ? posts.find(post => post.id === row.post_id)?.status === value : row[key] === value))
                    if (mode === 'insert') { const row = { revision: 0, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), ...values }; comments.push(row); selected = [row] }
                    if (mode === 'update') { if (conflict) selected = []; else selected.forEach(row => Object.assign(row, values)) }
                    if (mode === 'delete') { if (conflict) selected = []; else comments = comments.filter(row => !selected.includes(row)) }
                    selected = [...selected].sort((a, b) => {
                        for (const [key, ascending] of orders) { const result = String(a[key]).localeCompare(String(b[key])); if (result) return ascending ? result : -result }
                        return 0
                    })
                    const count = selected.length
                    const visibleColumns = columns.split(',').filter(column => !column.includes('!inner'))
                    const projected = selected.slice(start, end + 1).map(row => Object.fromEntries(visibleColumns.map(key => [key, row[key]])))
                    return Promise.resolve(resolve({ data: single ? projected[0] || null : projected, count, error: null }))
                },
            }
            return query
        }),
    }
}
function request(method = 'GET', payload?: unknown, admin = false, cookie = true, path = '') {
    const headers: Record<string, string> = { origin: 'https://platform.test', 'content-type': 'application/json' }
    if (cookie) headers.cookie = `mp_session=${session}${admin ? '; mp_admin_session=test-admin-token' : ''}`
    return new NextRequest(`https://platform.test/api/board/${postId}/comments${path}`, { method, headers, body: payload === undefined ? undefined : JSON.stringify(payload) })
}
const params = (id = postId, commentId = '') => ({ params: Promise.resolve({ id, commentId }) })
async function add() {
    const response = await create(request('POST', input), params())
    expect(response.status).toBe(201)
    return (await response.json()).comment
}
afterEach(() => { vi.unstubAllEnvs() })
beforeEach(async () => {
    vi.clearAllMocks()
    posts = [{ id: postId, status: 'published', attachments: [] }, { id: otherPost, status: 'published', attachments: [] }]
    comments = []; conflict = false; denyRate = false; insertError = null; deleteError = null; unpublishOnList = false
    vi.stubEnv('SESSION_SECRET', 'test-comment-session-secret')
    vi.stubEnv('BOARD_ENABLED', 'true'); vi.stubEnv('INTERNAL_DOCUMENTS_ENABLED', 'false')
    vi.stubEnv('NEXT_PUBLIC_USE_V2_DB', 'false'); vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', 'https://fixture.supabase.co')
    vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY', 'test-service-role'); vi.stubEnv('ADMIN_USER_IDS', 'board-admin')
    db = fakeDb(); mocks.createClient.mockReturnValue(db)
    session = await signSession({ iat: 1, exp: Math.floor(Date.now() / 1000) + 3600 })
})
describe('comment authentication, data boundary and lifecycle', () => {
    it('rejects missing sessions, cross-origin mutations and disabled board before DB access', async () => {
        expect((await list(request('GET', undefined, false, false), params())).status).toBe(401)
        const foreign = request('POST', input); foreign.headers.set('origin', 'https://other.test')
        expect((await create(foreign, params())).status).toBe(403)
        vi.stubEnv('BOARD_ENABLED', 'false')
        expect((await create(request('POST', input), params())).status).toBe(503)
        expect(mocks.createClient).not.toHaveBeenCalled()
    })
    it('creates a salted hash, strips secrets in every response and uses no-store', async () => {
        vi.stubEnv('ADMIN_USER_IDS', '')
        const comment = await add()
        expect(await verifyBoardPassword(password, comments[0].password_hash as string)).toBe(true)
        expect(comment).toMatchObject({ post_id: postId, body: input.body, revision: 0 })
        expect(JSON.stringify(comment)).not.toMatch(/password|scrypt-v1/)
        const response = await list(request(), params())
        expect(response.headers.get('cache-control')).toBe('private, no-store')
        const result = await response.json()
        expect(result.comments).toEqual([comment]); expect(result.total).toBe(1)
        expect(JSON.stringify(result)).not.toMatch(/password|scrypt-v1/)
    })
    it('uses only this published parent and denies all comment operations on drafts, even to admins', async () => {
        const comment = await add(); posts[0].status = 'draft'
        expect((await list(request(), params())).status).toBe(404)
        expect((await list(request('GET', undefined, true), params())).status).toBe(404)
        expect((await create(request('POST', input), params())).status).toBe(404)
        expect((await update(request('PATCH', { body: '수정', password, revision: 0 }), params(postId, comment.id))).status).toBe(404)
        expect((await remove(request('DELETE', { password, revision: 0 }), params(postId, comment.id))).status).toBe(404)
        expect(comments).toHaveLength(1)
    })
    it('keeps comments hidden if the parent becomes a draft between parent lookup and list query', async () => {
        await add(); unpublishOnList = true
        expect((await (await list(request(), params())).json()).comments).toEqual([])
    })
    it('checks the comment password for edits and deletion, then detects stale revisions', async () => {
        const comment = await add()
        expect((await update(request('PATCH', { body: '변경', password: 'wrong-password', revision: 0 }), params(postId, comment.id))).status).toBe(403)
        expect((await remove(request('DELETE', { password: 'wrong-password', revision: 0 }), params(postId, comment.id))).status).toBe(403)
        const response = await update(request('PATCH', { body: '변경', password, revision: 0 }), params(postId, comment.id))
        expect(response.status).toBe(200)
        expect((await response.json()).comment).toMatchObject({ body: '변경', author_name: input.author_name, revision: 1 })
        expect((await update(request('PATCH', { body: '덮어쓰기', password, revision: 0 }), params(postId, comment.id))).status).toBe(409)
        expect((await remove(request('DELETE', { password, revision: 0 }), params(postId, comment.id))).status).toBe(409)
        expect((await remove(request('DELETE', { password, revision: 1 }), params(postId, comment.id))).status).toBe(200)
        expect(comments).toHaveLength(0)
    })
    it('does not permit a valid password to target a comment from a different parent', async () => {
        const comment = await add()
        expect((await update(request('PATCH', { body: '변경', password, revision: 0 }), params(otherPost, comment.id))).status).toBe(404)
        expect((await remove(request('DELETE', { password, revision: 0 }, true), params(otherPost, comment.id))).status).toBe(404)
        expect(comments[0].body).toBe(input.body)
    })
    it('permits verified admin moderation but never trusts a forged administrator identity', async () => {
        const comment = await add()
        db.auth.getUser.mockResolvedValueOnce({ data: { user: { id: 'someone-else' } }, error: null })
        expect((await remove(request('DELETE', { password: '', revision: 0 }, true), params(postId, comment.id))).status).toBe(403)
        expect((await update(request('PATCH', { body: '관리자 수정', revision: 0 }, true), params(postId, comment.id))).status).toBe(200)
        expect((await remove(request('DELETE', { revision: 1 }, true), params(postId, comment.id))).status).toBe(200)
    })
    it('rejects empty/oversized/unknown fields and malformed ids/pages', async () => {
        for (const change of [{ body: '  ' }, { body: 'x'.repeat(2001) }, { author_name: 'x'.repeat(41) }, { password: 'short' }, { password_hash: 'spoof' }]) {
            expect((await create(request('POST', { ...input, ...change }), params())).status).toBe(400)
        }
        expect((await create(request('POST', input), params('invalid'))).status).toBe(404)
        expect((await list(request('GET', undefined, false, true, '?page=0'), params())).status).toBe(400)
        const comment = await add()
        expect((await update(request('PATCH', { body: '수정', password, revision: -1 }), params(postId, comment.id))).status).toBe(400)
        expect((await update(request('PATCH', { body: '수정', password, revision: 0, author_name: '위조' }), params(postId, comment.id))).status).toBe(400)
        expect((await remove(request('DELETE', { password, revision: 0 }), params(postId, 'invalid'))).status).toBe(404)
    })
    it('applies mutation and per-comment password limits and detects a concurrent CAS failure', async () => {
        const comment = await add(); denyRate = true
        expect((await update(request('PATCH', { body: '수정', password, revision: 0 }), params(postId, comment.id))).status).toBe(429)
        denyRate = false; conflict = true
        expect((await update(request('PATCH', { body: '수정', password, revision: 0 }), params(postId, comment.id))).status).toBe(409)
        expect((await remove(request('DELETE', { password, revision: 0 }), params(postId, comment.id))).status).toBe(409)
        expect(db.rpc.mock.calls.some(call => call[0] === 'board_rate_limit' && call[1].p_limit === 10)).toBe(true)
        expect(comments[0].revision).toBe(0)
        conflict = false
        db.rpc.mockImplementation(async (_name, args) => ({ data: args.p_limit !== 10, error: null }))
        expect((await remove(request('DELETE', { password, revision: 0 }), params(postId, comment.id))).status).toBe(429)
        expect(comments).toHaveLength(1)
    })
    it('paginates deterministically and isolates other posts', async () => {
        comments = Array.from({ length: 25 }, (_, index) => ({ id: String(index).padStart(3, '0'), post_id: postId, body: '의견', author_name: '작성자', revision: 0, created_at: '2026-10-09T00:00:00Z', updated_at: '2026-10-09T00:00:00Z' }))
        comments.push({ ...comments[0], post_id: otherPost })
        const first = await (await list(request(), params())).json()
        expect(first.comments).toHaveLength(20); expect(first.total).toBe(25); expect(first.comments[0].id).toBe('024')
        const second = await (await list(request('GET', undefined, false, true, '?page=2'), params())).json()
        expect(second.comments).toHaveLength(5); expect(second.page).toBe(2)
    })
    it('maps a concurrent parent unpublish to a safe error and never returns DB details', async () => {
        const comment = await add(); deleteError = '23514'
        const deletion = await remove(request('DELETE', { password, revision: 0 }), params(postId, comment.id))
        expect(deletion.status).toBe(404); expect(await deletion.json()).toEqual({ error: 'not_found' })
        expect(comments).toHaveLength(1)
        insertError = '23514'
        const response = await create(request('POST', input), params())
        expect(response.status).toBe(404); expect(await response.json()).toEqual({ error: 'not_found' })
        insertError = 'unexpected'
        expect((await create(request('POST', input), params())).status).toBe(503)
    })
})
