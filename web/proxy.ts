import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { verifySession } from '@/lib/auth'

const SESSION_COOKIE_NAME = 'mp_session'

export async function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl

    // Whitelist: login page, login API, Next internals, static files
    if (
        pathname === '/login' ||
        pathname.startsWith('/login/') ||
        pathname === '/api/auth/login' ||
        pathname.startsWith('/_next') ||
        pathname.includes('.')
    ) {
        return NextResponse.next()
    }

    const sessionCookie = request.cookies.get(SESSION_COOKIE_NAME)
    const payload = await verifySession(sessionCookie?.value)

    if (!payload) {
        if (pathname.startsWith('/api/')) {
            return NextResponse.json({ error: 'unauthorized' }, { status: 401 })
        }
        return NextResponse.redirect(new URL('/login', request.url))
    }

    return NextResponse.next()
}

export const config = {
    matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
