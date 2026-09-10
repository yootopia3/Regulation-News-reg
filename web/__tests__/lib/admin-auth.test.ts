import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

const { getUser, createClient } = vi.hoisted(() => ({ getUser: vi.fn(), createClient: vi.fn() }))
vi.mock('@supabase/supabase-js', () => ({ createClient }))
import { adminClient, requireAdmin, verifyAdmin, assertOrigin, boundedBody, adminFailure } from '@/lib/admin-auth'

beforeEach(() => {
    vi.unstubAllEnvs(); vi.clearAllMocks()
    vi.stubEnv('INTERNAL_DOCUMENTS_ENABLED', 'true')
    vi.stubEnv('NEXT_PUBLIC_USE_V2_DB', 'true')
    vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL_V2', 'https://example.supabase.co')
    vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY', 'fixture-service-key')
    vi.stubEnv('ADMIN_USER_IDS', 'permitted-id')
    createClient.mockReturnValue({ auth: { getUser } })
})

describe('private document authorization', () => {
    it('never falls back to the anonymous key or an unset feature flag', () => {
        vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY', '')
        vi.stubEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY_V2', 'fixture-anon-key')
        expect(() => adminClient()).toThrow('not_configured')
        vi.stubEnv('INTERNAL_DOCUMENTS_ENABLED', 'false')
        expect(() => adminClient()).toThrow('disabled')
        expect(createClient).not.toHaveBeenCalled()
    })
    it('rejects a dashboard-only cookie without any provider lookup', async () => {
        const request = new NextRequest('https://site.test/api/admin/documents', { headers: { cookie: 'mp_session=ordinary' } })
        await expect(requireAdmin(request)).rejects.toMatchObject({ status: 401 })
        expect(getUser).not.toHaveBeenCalled()
    })
    it('validates the token remotely and then applies the server allowlist', async () => {
        getUser.mockResolvedValue({ data: { user: { id: 'other-id' } }, error: null })
        await expect(verifyAdmin('supabase-token')).rejects.toMatchObject({ status: 403 })
        getUser.mockResolvedValue({ data: { user: { id: 'permitted-id' } }, error: null })
        expect((await verifyAdmin('supabase-token')).userId).toBe('permitted-id')
        expect(getUser).toHaveBeenCalledWith('supabase-token')
    })
    it('rejects a revoked or forged token', async () => {
        getUser.mockResolvedValue({ data: { user: null }, error: new Error('invalid') })
        await expect(verifyAdmin('forged')).rejects.toMatchObject({ status: 401 })
    })
    it('rejects missing or cross-site origins for writes', async () => {
        expect(() => assertOrigin(new Request('https://site.test/api/admin/login', { method: 'POST' }))).toThrow('invalid_origin')
        const request = new NextRequest('https://site.test/api/admin/documents', { method: 'POST', headers: { origin: 'https://attacker.test', cookie: 'mp_admin_session=token' } })
        await expect(requireAdmin(request)).rejects.toMatchObject({ status: 403 })
        expect(getUser).not.toHaveBeenCalled()
    })
    it('enforces streaming limits without trusting content-length', async () => {
        const request = new Request('https://site.test', { method: 'POST', body: '123456789' })
        await expect(boundedBody(request, 4)).rejects.toMatchObject({ status: 413 })
    })
    it('does not expose provider exception contents', async () => {
        const response = adminFailure(new Error('PRIVATE DOCUMENT SENTINEL'))
        expect(await response.json()).toEqual({ error: 'request_failed' })
        expect(response.headers.get('cache-control')).toBe('private, no-store')
    })
})
