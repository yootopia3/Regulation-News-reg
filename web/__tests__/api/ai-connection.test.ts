// @vitest-environment node
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { NextRequest } from 'next/server'
const { db, query, verify, provider } = vi.hoisted(() => ({ db: { from: vi.fn(), rpc: vi.fn() },
    query: { select: vi.fn(), eq: vi.fn(), maybeSingle: vi.fn() }, verify: vi.fn(), provider: vi.fn() }))
vi.mock('@supabase/supabase-js', () => ({ createClient: () => ({ ...db, auth: { getUser: verify } }) }))
vi.mock('@/lib/ai-connection/network', async original => ({ ...await original<object>(), providerRequest: provider }))
import { GET, POST } from '@/app/api/admin/ai-connection/route'
import { POST as test } from '@/app/api/admin/ai-connection/test/route'
import { POST as models } from '@/app/api/admin/ai-connection/models/route'
import { encryptKey, decryptKey, makeReceipt, checkReceipt, type ConnectionRow } from '@/lib/ai-connection/server'
import { AdminError } from '@/lib/admin-auth'
const input = { base_url: 'https://ai.example.test/v1', protocol: 'chat_completions' as const, model: 'synthetic-model', api_key: 'synthetic-' + 'unit'.repeat(12), revision: 0 }
function request(body?: object, admin = true, origin = 'https://site.test') {
    return new NextRequest('https://site.test/api/admin/ai-connection', { method: body ? 'POST' : 'GET', headers: { origin, cookie: admin ? 'mp_admin_session=fixture' : 'mp_session=ordinary' }, body: body ? JSON.stringify(body) : undefined })
}
function stored(): ConnectionRow { return { base_url: input.base_url, protocol: input.protocol, model: input.model, revision: 1,
    api_key_ciphertext: encryptKey(input.api_key, input.base_url), key_last4: input.api_key.slice(-4), updated_at: '2026-11-02T00:00:00Z' } }
beforeEach(() => {
    vi.clearAllMocks()
    for (const [key, value] of Object.entries({ INTERNAL_DOCUMENTS_ENABLED: 'true', SANCTION_AI_SETTINGS_ENABLED: 'true', AI_CONNECTION_ENCRYPTION_KEY: 'ab'.repeat(32),
        NEXT_PUBLIC_SUPABASE_URL: 'https://example.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'fixture', ADMIN_USER_IDS: 'admin' })) vi.stubEnv(key, value)
    verify.mockResolvedValue({ data: { user: { id: 'admin' } }, error: null })
    db.from.mockReturnValue(query); query.select.mockReturnValue(query); query.eq.mockReturnValue(query)
    query.maybeSingle.mockResolvedValue({ data: null, error: null })
    db.rpc.mockResolvedValue({ data: 1, error: null })
    provider.mockResolvedValue({ choices: [{ finish_reason: 'stop', message: { content: '{"ok":true}' } }] })
})
afterEach(() => { vi.unstubAllEnvs(); vi.useRealTimers() })
describe('AI connection administrative boundary', () => {
    it('denies ordinary sessions, non-admins and foreign Origins before I/O', async () => {
        expect((await GET(request(undefined, false))).status).toBe(401)
        for (const route of [POST, test, models]) expect((await route(request(input, false))).status).toBe(401)
        expect((await test(request(input, true, 'https://other.test'))).status).toBe(403)
        verify.mockResolvedValueOnce({ data: { user: { id: 'other' } }, error: null })
        expect((await GET(request())).status).toBe(403)
        expect(db.from).not.toHaveBeenCalled(); expect(provider).not.toHaveBeenCalled()
    })
    it('returns only metadata, never plaintext or ciphertext, with no-store', async () => {
        const row = stored(); query.maybeSingle.mockResolvedValue({ data: row })
        const response = await GET(request()); const data = await response.json()
        expect(data).toMatchObject({ configured: true, key_last4: row.key_last4, revision: 1 })
        expect(JSON.stringify(data)).not.toContain(input.api_key)
        expect(JSON.stringify(data)).not.toContain(row.api_key_ciphertext)
        expect(response.headers.get('cache-control')).toContain('no-store')
        expect(decryptKey(row)).toBe(input.api_key)
        expect(() => decryptKey({ ...row, base_url: 'https://other.test/v1' })).toThrow('connection_not_configured')
        vi.stubEnv('AI_CONNECTION_ENCRYPTION_KEY', 'cd'.repeat(32))
        expect(() => decryptKey(row)).toThrow('connection_not_configured')
    })
    it('tests a synthetic JSON request and stores encrypted settings after a successful test', async () => {
        const response = await test(request(input)); const { receipt } = await response.json()
        expect(response.status).toBe(200)
        expect(provider).toHaveBeenCalledWith(input.base_url, 'chat/completions', input.api_key, expect.objectContaining({ model: input.model, messages: expect.any(Array) }))
        expect(provider.mock.calls[0][3].max_tokens).toBe(12000)
        const saved = await POST(request({ input, receipt })); expect(saved.status).toBe(200)
        const call = db.rpc.mock.calls.find(([name]) => name === 'sanction_ai_connection_save')!
        expect(JSON.stringify(call)).not.toContain(input.api_key)
        expect(call[1]).toMatchObject({ p_actor: 'admin', p_revision: 0, p_last4: input.api_key.slice(-4) })
        expect(decryptKey({ ...stored(), api_key_ciphertext: call[1].p_ciphertext })).toBe(input.api_key)
    })
    it('binds a short-lived receipt to every setting, key, revision and actor', () => {
        const receipt = makeReceipt(input, 'admin')
        expect(() => checkReceipt(input, 'admin', receipt)).not.toThrow()
        for (const patch of [{ model: 'other' }, { base_url: 'https://other.test/v1' }, { api_key: 'changed' }, { revision: 1 }, { protocol: 'responses' as const }]) {
            expect(() => checkReceipt({ ...input, ...patch }, 'admin', receipt)).toThrow('connection_test_required')
        }
        expect(() => checkReceipt(input, 'other', receipt)).toThrow('connection_test_required')
        vi.useFakeTimers(); vi.setSystemTime(Date.now() + 600001)
        expect(() => checkReceipt(input, 'admin', receipt)).toThrow('connection_test_required')
    })
    it('keeps a blank key only for the same saved address and rejects stale revisions', async () => {
        query.maybeSingle.mockResolvedValue({ data: stored() })
        expect((await test(request({ ...input, api_key: '', revision: 1 }))).status).toBe(200)
        expect(provider.mock.calls[0][2]).toBe(input.api_key)
        provider.mockClear()
        expect((await test(request({ ...input, api_key: '', base_url: 'https://other.test/v1', revision: 1 }))).status).toBe(400)
        expect((await test(request(input))).status).toBe(409)
        expect(provider).not.toHaveBeenCalled()
    })
    it('does not save untested/changed settings or swallow DB conflicts', async () => {
        const receipt = makeReceipt(input, 'admin')
        expect((await POST(request({ input: { ...input, model: 'other' }, receipt }))).status).toBe(400)
        expect(db.rpc.mock.calls.some(([name]) => name === 'sanction_ai_connection_save')).toBe(false)
        db.rpc.mockImplementation((name: string) => Promise.resolve(name === 'sanction_ai_connection_save' ? { error: { code: '40001' } } : { data: true }))
        expect((await POST(request({ input, receipt }))).status).toBe(409)
    })
    it('validates both provider formats; never leaks raw provider error text', async () => {
        provider.mockResolvedValueOnce({ status: 'completed', output: [{ type: 'message', content: [{ type: 'output_text', text: '{"ok":true}' }] }] })
        expect((await test(request({ ...input, protocol: 'responses' }))).status).toBe(200)
        expect(provider.mock.calls[0][3].max_output_tokens).toBe(12000)
        for (const raw of [{ choices: [] }, { choices: [{ finish_reason: 'length', message: { content: '{"ok":true}' } }] }, { choices: [{ finish_reason: 'stop', message: { content: 'PRIVATE_CANARY' } }] }]) {
            provider.mockResolvedValueOnce(raw)
            const response = await test(request(input)); expect(response.status).toBe(502)
            expect(await response.text()).not.toContain('PRIVATE_CANARY')
        }
        provider.mockRejectedValueOnce(new Error('PRIVATE_CANARY'))
        expect(await (await test(request(input))).text()).not.toContain('PRIVATE_CANARY')
        provider.mockRejectedValueOnce(new AdminError(502, 'provider_auth_failed'))
        expect(await (await test(request(input))).json()).toEqual({ error: 'provider_auth_failed' })
    })
    it('queries model IDs without requiring a model, and applies feature/config gates', async () => {
        provider.mockResolvedValueOnce({ data: [{ id: 'model-b' }, { id: 'model-a' }, { id: 'model-a' }] })
        expect(await (await models(request({ ...input, model: '' }))).json()).toEqual({ models: ['model-a', 'model-b'] })
        vi.stubEnv('SANCTION_AI_SETTINGS_ENABLED', 'false')
        expect((await (await GET(request())).json()).available).toBe(false)
        expect((await test(request(input))).status).toBe(503)
        vi.stubEnv('SANCTION_AI_SETTINGS_ENABLED', 'true'); vi.stubEnv('AI_CONNECTION_ENCRYPTION_KEY', '')
        expect((await test(request(input))).status).toBe(503)
    })
})
