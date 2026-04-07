import { NextResponse } from 'next/server'
import { signSession } from '@/lib/auth'

const SESSION_COOKIE_NAME = 'mp_session'
const SESSION_MAX_AGE_SECONDS = 86400

function timingSafeEqualString(a: string, b: string): boolean {
    const len = Math.max(a.length, b.length)
    let diff = a.length ^ b.length
    for (let i = 0; i < len; i++) {
        const ca = i < a.length ? a.charCodeAt(i) : 0
        const cb = i < b.length ? b.charCodeAt(i) : 0
        diff |= ca ^ cb
    }
    return diff === 0
}

export async function POST(request: Request) {
    const appPasscode = process.env.APP_PASSCODE
    const sessionSecret = process.env.SESSION_SECRET

    if (!appPasscode || !sessionSecret) {
        console.error('[/api/auth/login] APP_PASSCODE or SESSION_SECRET not set')
        return NextResponse.json({ ok: false, error: 'auth not configured' }, { status: 500 })
    }

    let body: unknown
    try {
        body = await request.json()
    } catch {
        return NextResponse.json({ ok: false }, { status: 401 })
    }

    const passcode =
        typeof body === 'object' && body !== null && typeof (body as { passcode?: unknown }).passcode === 'string'
            ? (body as { passcode: string }).passcode
            : ''

    if (!timingSafeEqualString(passcode, appPasscode)) {
        return NextResponse.json({ ok: false }, { status: 401 })
    }

    const now = Math.floor(Date.now() / 1000)
    const token = await signSession({ iat: now, exp: now + SESSION_MAX_AGE_SECONDS })

    const response = NextResponse.json({ ok: true }, { status: 200 })
    response.cookies.set({
        name: SESSION_COOKIE_NAME,
        value: token,
        httpOnly: true,
        secure: true,
        sameSite: 'lax',
        path: '/',
        maxAge: SESSION_MAX_AGE_SECONDS,
    })
    return response
}
