// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
const mocks = vi.hoisted(() => ({ createClient: vi.fn() }))
vi.mock('@supabase/supabase-js', () => ({ createClient: mocks.createClient }))
import { signSession } from '@/lib/auth'
import { GET as list, POST as create } from '@/app/api/board/route'
import { GET as detail, PATCH as update, DELETE as remove } from '@/app/api/board/[id]/route'
import { POST as unlock } from '@/app/api/board/[id]/unlock/route'
import { GET as download } from '@/app/api/board/[id]/attachments/[attachmentId]/route'
import { POST as adminLogin } from '@/app/api/admin/login/route'
import { fileMime } from '@/lib/board/server'
import { hashBoardPassword, verifyBoardPassword } from '@/lib/board/password'

type Row = Record<string, unknown>
let rows: Row[]
let session: string
let objects: Map<string, Uint8Array>
let denyRate: boolean
let conflict: boolean
let db: ReturnType<typeof fakeDatabase>
const password = 'test-board-password'
const payload = { author_name: '홍길동', title: '업무 안내', body: '확인할 내용입니다.', category: 'general', status: 'published', password, keepAttachmentIds: [], is_pinned: false }
function fakeDatabase() {
    return {
        auth: { getUser: vi.fn().mockResolvedValue({ data: { user: { id: 'board-admin' } }, error: null }), signInWithPassword: vi.fn().mockResolvedValue({ data: { user: { id: 'board-admin' }, session: { access_token: 'admin-token', expires_at: Math.floor(Date.now()/1000) + 3600 } }, error: null }) },
        rpc: vi.fn(async (name: string, args: unknown) => { void name; void args; return { data: !denyRate, error: null } }),
        from: vi.fn(() => {
            let columns = '*', mode = 'read', values: Row = {}, single = false
            const filters: Array<[string, unknown]> = []
            let start = 0, end = 19
            const query = {
                select: (value: string) => { columns = value; return query },
                eq: (key: string, value: unknown) => { filters.push([key, value]); return query },
                order: () => query, or: () => query,
                range: (a: number, b: number) => { start = a; end = b; return query },
                maybeSingle: () => { single = true; return query }, single: () => { single = true; return query },
                insert: (value: Row) => { values = value; mode = 'insert'; return query },
                update: (value: Row) => { values = value; mode = 'update'; return query }, delete: () => { mode = 'delete'; return query },
                then: (resolve: (value: unknown) => unknown) => {
                    let selected = rows.filter(row => filters.every(([key, value]) => row[key] === value))
                    if (mode === 'insert') { const row = { revision: 0, created_at: new Date().toISOString(), ...values }; rows.push(row); selected = [row] }
                    if (mode === 'update') { if (conflict) selected = []; else selected.forEach(row => Object.assign(row, values)) }
                    if (mode === 'delete') { if (conflict) selected = []; else rows = rows.filter(row => !selected.includes(row)) }
                    const count = selected.length
                    const projected = selected.slice(start, end+1).map(row => columns === '*' ? row : Object.fromEntries(columns.split(',').map(key => [key,row[key]])))
                    return Promise.resolve(resolve({ data: single ? projected[0] || null : projected, count, error: null }))
                },
            }
            return query
        }),
        storage: { from: vi.fn(() => ({
            upload: vi.fn(async (path: string, bytes: Uint8Array) => { objects.set(path, bytes); return { error: null } }),
            remove: vi.fn(async (paths: string[]) => { paths.forEach(path => objects.delete(path)); return { error: null } }),
            download: vi.fn(async (path: string) => ({ data: objects.has(path) ? new Blob([Buffer.from(objects.get(path)!)]) : null, error: null })),
        })) },
    }
}
function request(path: string, method = 'GET', body?: BodyInit, admin = false, cookie = true) {
    const headers: Record<string,string> = { origin: 'https://platform.test' }
    if (cookie) headers.cookie = `mp_session=${session}${admin ? '; mp_admin_session=admin-token' : ''}`
    if (typeof body === 'string') headers['content-type'] = 'application/json'
    return new NextRequest(`https://platform.test/api/board${path}`, { method, headers, body })
}
function form(overrides: Row = {}, attachment?: File) {
    const result = new FormData(); result.set('payload', JSON.stringify({ ...payload, ...overrides }))
    if (attachment) result.append('files', attachment)
    return result
}
const params = (id: string) => ({ params: Promise.resolve({ id }) })
async function add(overrides: Row = {}, attachment?: File) {
    const response = await create(request('', 'POST', form(overrides, attachment)))
    expect(response.status).toBe(201)
    return (await response.json()).post
}
beforeEach(async () => {
    vi.unstubAllEnvs(); vi.clearAllMocks(); rows = []; objects = new Map(); denyRate = false; conflict = false
    vi.stubEnv('SESSION_SECRET', 'test-session-secret-for-board')
    vi.stubEnv('BOARD_ENABLED', 'true'); vi.stubEnv('INTERNAL_DOCUMENTS_ENABLED', 'false')
    vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', 'https://fixture.supabase.co')
    vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY', 'test-service-role')
    vi.stubEnv('ADMIN_USER_IDS', 'board-admin')
    db = fakeDatabase(); mocks.createClient.mockReturnValue(db)
    session = await signSession({ iat: 1, exp: Math.floor(Date.now()/1000)+3600 })
})
describe('board permissions and lifecycle', () => {
    it('rejects missing sessions and cross-origin writes before database access', async () => {
        expect((await list(request('', 'GET', undefined, false, false))).status).toBe(401)
        const input = request('', 'POST', form()); input.headers.set('origin','https://other.test')
        expect((await create(input)).status).toBe(403)
        expect(mocks.createClient).not.toHaveBeenCalled()
    })
    it('is separately gated and does not require admin configuration for ordinary writers', async () => {
        vi.stubEnv('ADMIN_USER_IDS', '')
        await add()
        vi.stubEnv('BOARD_ENABLED', 'false')
        expect((await list(request(''))).status).toBe(503)
    })
    it('stores salted hashes and never exposes hashes or storage paths in responses', async () => {
        const post = await add({}, new File(['%PDF-1.7\nfixture'], '자료.pdf'))
        expect(await verifyBoardPassword(password, rows[0].password_hash as string)).toBe(true)
        expect(rows[0].password_hash).not.toContain(password)
        expect(JSON.stringify(post)).not.toMatch(/password_hash|scrypt-v1|"path"|"mime"/)
        expect(post.attachments[0].name).toBe('자료.pdf')
        const result = await (await list(request(''))).json()
        expect(result.posts[0]).not.toHaveProperty('body')
        expect(JSON.stringify(result)).not.toContain('password_hash')
    })
    it('keeps drafts out of lists, detail, and attachment downloads but permits password unlocking', async () => {
        const post = await add({ status: 'draft' }, new File(['%PDF-1.7'], 'draft.pdf'))
        expect((await (await list(request(''))).json()).posts).toHaveLength(0)
        expect((await detail(request(`/${post.id}`), params(post.id))).status).toBe(404)
        expect((await download(request(''), { params: Promise.resolve({ id: post.id, attachmentId: post.attachments[0].id }) })).status).toBe(404)
        const opened = await unlock(request('', 'POST', JSON.stringify({ password })), params(post.id))
        expect(opened.status).toBe(200)
        expect((await opened.json()).post.body).toBe(payload.body)
    })
    it('checks passwords for modification and deletion and detects a stale revision', async () => {
        const post = await add()
        expect((await update(request('', 'PATCH', form({ revision: 0, password: 'wrong-password' })), params(post.id))).status).toBe(403)
        expect((await remove(request('', 'DELETE', JSON.stringify({ password: 'wrong-password', revision: 0 })), params(post.id))).status).toBe(403)
        expect(rows).toHaveLength(1)
        const response = await update(request('', 'PATCH', form({ title: '수정된 안내', revision: 0 })), params(post.id))
        expect(response.status).toBe(200); expect(rows[0].revision).toBe(1)
        expect((await update(request('', 'PATCH', form({ revision: 0 })), params(post.id))).status).toBe(409)
    })
    it('prevents ordinary clients from pinning or creating notices and permits verified administrators', async () => {
        expect((await create(request('', 'POST', form({ is_pinned: true })))).status).toBe(403)
        expect((await create(request('', 'POST', form({ category: 'notice' })))).status).toBe(403)
        const post = await add()
        expect((await update(request('', 'PATCH', form({ revision: 0, password: '', is_pinned: true, category: 'notice' }), true), params(post.id))).status).toBe(200)
        expect(rows[0].is_pinned).toBe(true)
        expect(db.auth.getUser).toHaveBeenCalledWith('admin-token')
    })
    it('does not grant admin rights to a forged or revoked admin cookie', async () => {
        db.auth.getUser.mockResolvedValueOnce({ data: { user: { id: 'not-admin' } }, error: null })
        expect((await create(request('', 'POST', form({ is_pinned: true }), true))).status).toBe(403)
    })
    it('enforces rate limits before expensive password work or changes', async () => {
        const post = await add(); denyRate = true
        expect((await unlock(request('', 'POST', JSON.stringify({ password })), params(post.id))).status).toBe(429)
        expect(rows[0].revision).toBe(0)
    })
    it('serves only attached files as downloads and makes deleted files inaccessible', async () => {
        const post = await add({}, new File(['%PDF-1.7'], '보고서.pdf'))
        const attachmentId = post.attachments[0].id
        const response = await download(request(''), { params: Promise.resolve({ id: post.id, attachmentId }) })
        expect(response.status).toBe(200)
        expect(response.headers.get('content-disposition')).toContain('attachment;')
        expect(response.headers.get('x-content-type-options')).toBe('nosniff')
        expect(response.headers.get('cache-control')).toBe('private, no-store')
        expect((await remove(request('', 'DELETE', JSON.stringify({ password, revision: 0 })), params(post.id))).status).toBe(200)
        expect(objects.size).toBe(0)
        expect((await download(request(''), { params: Promise.resolve({ id: post.id, attachmentId }) })).status).toBe(404)
    })
    it('rejects attachment spoofing, oversized uploads and foreign attachment ids', async () => {
        expect((await create(request('', 'POST', form({}, new File(['<script>alert(1)</script>'], 'fake.pdf'))))).status).toBe(400)
        expect((await create(request('', 'POST', form({}, new File(['%PDF-'+'x'.repeat(3*1024*1024)], 'big.pdf'))))).status).toBe(413)
        const post = await add()
        expect((await update(request('', 'PATCH', form({ revision: 0, keepAttachmentIds: ['00000000-0000-4000-8000-000000000001'] })), params(post.id))).status).toBe(400)
        expect(objects.size).toBe(0)
    })
    it('cleans up only new uploads on a concurrent update conflict', async () => {
        const post = await add({}, new File(['%PDF-1.7'], 'first.pdf'))
        conflict = true
        expect((await update(request('', 'PATCH', form({ revision: 0, keepAttachmentIds: [post.attachments[0].id] }, new File(['%PDF-1.7'], 'second.pdf'))), params(post.id))).status).toBe(409)
        expect(objects.size).toBe(1)
        expect(rows[0].revision).toBe(0)
    })
    it('lets board admins log in while the private documents feature stays disabled', async () => {
        const response = await adminLogin(request('', 'POST', JSON.stringify({ email: 'admin@example.test', password: 'test-admin-password', scope: 'board' })))
        expect(response.status).toBe(200)
        expect(response.headers.get('set-cookie')).toContain('mp_admin_session=')
        expect(db.rpc.mock.calls.some(call => call[0] === 'board_rate_limit')).toBe(true)
    })
})
describe('password and document format boundaries', () => {
    it('uses a random salt and rejects wrong passwords and malformed hashes', async () => {
        const first = await hashBoardPassword(password), second = await hashBoardPassword(password)
        expect(first).not.toBe(second)
        expect(await verifyBoardPassword(password, first)).toBe(true)
        expect(await verifyBoardPassword('different-password', first)).toBe(false)
        expect(await verifyBoardPassword(password, 'corrupt')).toBe(false)
    })
    it('accepts supported compound/ZIP formats but rejects executable extensions', () => {
        expect(fileMime('book.xlsx', new Uint8Array([0x50,0x4b,3,4]))).toContain('spreadsheetml')
        expect(fileMime('rules.hwp', Buffer.from('d0cf11e0a1b11ae1', 'hex'))).toBe('application/octet-stream')
        expect(() => fileMime('run.exe', new Uint8Array([0x50,0x4b,3,4]))).toThrow('invalid_file')
    })
})
