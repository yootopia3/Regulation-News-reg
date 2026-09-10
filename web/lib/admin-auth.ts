import { createClient } from '@supabase/supabase-js'
import { NextRequest, NextResponse } from 'next/server'
import { createHmac } from 'node:crypto'

export const ADMIN_COOKIE = 'mp_admin_session'
export const PRIVATE_HEADERS = { 'Cache-Control': 'private, no-store' }

export class AdminError extends Error {
    constructor(public status: number, public code: string) { super(code) }
}

export function adminClient() {
    if (process.env.INTERNAL_DOCUMENTS_ENABLED !== 'true') throw new AdminError(503, 'disabled')
    const v2 = process.env.NEXT_PUBLIC_USE_V2_DB === 'true'
    const url = v2 ? process.env.NEXT_PUBLIC_SUPABASE_URL_V2 : process.env.NEXT_PUBLIC_SUPABASE_URL
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY
    if (!url || !key || !process.env.ADMIN_USER_IDS?.trim()) throw new AdminError(503, 'not_configured')
    return createClient(url, key, {
        auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
        global: { fetch: (input, init) => fetch(input, { ...init, signal: AbortSignal.timeout(20000) }) },
    })
}

export async function adminRateLimit(db: ReturnType<typeof adminClient>, scope: string, identity: string, limit: number, seconds: number) {
    const key = createHmac('sha256', process.env.SUPABASE_SERVICE_ROLE_KEY || '').update(`${scope}:${identity}`).digest('hex')
    const { data, error } = await db.rpc('internal_admin_rate_limit', { p_key: key, p_limit: limit, p_seconds: seconds })
    if (error) throw new AdminError(503, 'not_configured')
    if (!data) throw new AdminError(429, 'rate_limited')
}

export function allowedAdmin(id: string) {
    return (process.env.ADMIN_USER_IDS || '').split(',').map(s => s.trim()).filter(Boolean).includes(id)
}

export async function verifyAdmin(token?: string) {
    if (!token) throw new AdminError(401, 'unauthorized')
    const db = adminClient()
    const { data, error } = await db.auth.getUser(token)
    if (error || !data.user) throw new AdminError(401, 'unauthorized')
    if (!allowedAdmin(data.user.id)) throw new AdminError(403, 'forbidden')
    return { db, userId: data.user.id }
}

export function assertOrigin(request: Request) {
    if (request.headers.get('origin') !== new URL(request.url).origin) throw new AdminError(403, 'invalid_origin')
}

export async function requireAdmin(request: NextRequest) {
    if (!['GET', 'HEAD'].includes(request.method)) assertOrigin(request)
    return verifyAdmin(request.cookies.get(ADMIN_COOKIE)?.value)
}

export function privateJson(body: unknown, status = 200) {
    return NextResponse.json(body, { status, headers: PRIVATE_HEADERS })
}

export function adminFailure(error: unknown) {
    // Do not log provider errors: they may contain document content or credentials.
    return privateJson({ error: error instanceof AdminError ? error.code : 'request_failed' }, error instanceof AdminError ? error.status : 500)
}

export async function boundedBody(request: Request, maxBytes: number): Promise<Uint8Array> {
    if (Number(request.headers.get('content-length')) > maxBytes) throw new AdminError(413, 'too_large')
    if (!request.body) throw new AdminError(400, 'empty_body')
    const reader = request.body.getReader()
    const chunks: Uint8Array[] = []
    let size = 0
    try {
        while (true) {
            const { value, done } = await reader.read()
            if (done) break
            size += value.byteLength
            if (size > maxBytes) { await reader.cancel(); throw new AdminError(413, 'too_large') }
            chunks.push(value)
        }
    } finally { reader.releaseLock() }
    const body = new Uint8Array(size)
    let offset = 0
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength }
    return body
}

export async function boundedJson(request: Request, maxBytes = 16384): Promise<unknown> {
    try { return JSON.parse(new TextDecoder().decode(await boundedBody(request, maxBytes))) }
    catch (error) { if (error instanceof AdminError) throw error; throw new AdminError(400, 'invalid_json') }
}
