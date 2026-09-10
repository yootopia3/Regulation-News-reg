import { z } from 'zod'
import { ADMIN_COOKIE, AdminError, adminClient, adminRateLimit, allowedAdmin, assertOrigin, boundedJson, privateJson, adminFailure } from '@/lib/admin-auth'

export async function POST(request: Request) {
    try {
        assertOrigin(request)
        const input = z.object({ email: z.string().email().max(254), password: z.string().min(1).max(256) }).strict().safeParse(await boundedJson(request, 4096))
        if (!input.success) throw new AdminError(400, 'invalid_credentials')
        const db = adminClient()
        await adminRateLimit(db, 'login', 'global', 30, 60)
        await adminRateLimit(db, 'login-email', input.data.email.trim().toLowerCase(), 5, 600)
        const { data, error } = await db.auth.signInWithPassword(input.data)
        if (error || !data.session || !data.user || !allowedAdmin(data.user.id)) throw new AdminError(401, 'invalid_credentials')
        const response = privateJson({ ok: true })
        response.cookies.set(ADMIN_COOKIE, data.session.access_token, {
            httpOnly: true, secure: new URL(request.url).protocol === 'https:', sameSite: 'strict', path: '/',
            maxAge: Math.max(0, Math.min(3600, (data.session.expires_at || 0) - Math.floor(Date.now() / 1000))),
        })
        return response
    } catch (error) { return adminFailure(error) }
}
