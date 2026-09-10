import { ADMIN_COOKIE, assertOrigin, privateJson, adminFailure } from '@/lib/admin-auth'

export async function POST(request: Request) {
    try {
        assertOrigin(request)
        const response = privateJson({ ok: true })
        response.cookies.set(ADMIN_COOKIE, '', { httpOnly: true, sameSite: 'strict', path: '/', maxAge: 0 })
        return response
    } catch (error) { return adminFailure(error) }
}
