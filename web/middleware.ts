import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
    // Check for auth cookie
    const authCookie = request.cookies.get('auth_token')
    const { pathname } = request.nextUrl

    // Allow access to login page and public assets
    if (
        pathname.startsWith('/login') ||
        pathname.startsWith('/_next') ||
        pathname.includes('.') // public files like images
    ) {
        return NextResponse.next()
    }

    // If no auth cookie, redirect to login
    if (!authCookie || authCookie.value !== 'valid') {
        return NextResponse.redirect(new URL('/login', request.url))
    }

    return NextResponse.next()
}

export const config = {
    matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
