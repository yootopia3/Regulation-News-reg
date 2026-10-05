import { randomUUID } from 'node:crypto'
import { NextRequest } from 'next/server'
import { z } from 'zod'
import { ADMIN_COOKIE, AdminError, adminRateLimit, assertOrigin, boundedBody, serviceClient, verifyAdmin } from '@/lib/admin-auth'
import { verifySession } from '@/lib/auth'
import { hashBoardPassword, verifyBoardPassword } from './password'
import { BOARD_PAGE_SIZE, MAX_ATTACHMENTS, MAX_ATTACHMENT_BYTES, type BoardPost } from './types'

export const BOARD_BUCKET = 'board-attachments'
export const PUBLIC_COLUMNS = 'id,author_name,title,body,category,status,is_pinned,revision,created_at,updated_at,published_at,attachments'
const LIST_COLUMNS = PUBLIC_COLUMNS.split(',').filter(column => column !== 'body').join(',')
export type StoredAttachment = { id: string; name: string; size: number; path: string; mime: string }
export type StoredPost = Omit<BoardPost, 'attachments'> & { password_hash: string; attachments: StoredAttachment[] }
export type BoardContext = { db: ReturnType<typeof serviceClient>; isAdmin: boolean; session: string }
const uuid = z.string().uuid()
export function validId(value: string) {
    if (!uuid.safeParse(value).success) throw new AdminError(404, 'not_found')
    return value
}
export const passwordSchema = z.string().min(8).max(128)
const postSchema = z.object({
    author_name: z.string().trim().min(1).max(40), title: z.string().trim().min(1).max(150),
    body: z.string().trim().min(1).max(20000), category: z.enum(['general', 'notice', 'resources']),
    status: z.enum(['draft', 'published']), password: z.string().max(128).default(''),
    revision: z.number().int().nonnegative().optional(),
    keepAttachmentIds: z.array(uuid).max(MAX_ATTACHMENTS).default([]),
    is_pinned: z.boolean().default(false),
}).strict()
export type PostInput = z.infer<typeof postSchema>
export function publicPost<T extends { attachments: StoredAttachment[]; password_hash?: string }>(post: T) {
    // Explicit column selection is used for all queries, and private fields are stripped here again.
    const { password_hash: _hash, attachments, ...visible } = post
    void _hash
    return { ...visible, attachments: attachments.map(({ id, name, size }) => ({ id, name, size })) }
}
export async function boardContext(request: NextRequest): Promise<BoardContext> {
    const session = request.cookies.get('mp_session')?.value
    if (!await verifySession(session)) throw new AdminError(401, 'unauthorized')
    if (!['GET', 'HEAD'].includes(request.method)) assertOrigin(request)
    if (process.env.BOARD_ENABLED !== 'true') throw new AdminError(503, 'disabled')
    const db = serviceClient()
    let isAdmin = false
    if (request.cookies.get(ADMIN_COOKIE)?.value) {
        try { await verifyAdmin(request.cookies.get(ADMIN_COOKIE)?.value, 'board'); isAdmin = true } catch { /* A revoked admin token never grants privileges. */ }
    }
    // Tokens and identities are HMACed by the limiter; no raw credentials/IPs are stored.
    if (!['GET', 'HEAD'].includes(request.method)) {
        await adminRateLimit(db, 'board-write', session!, 30, 60, 'board_rate_limit')
        await adminRateLimit(db, 'board-write-global', 'global', 300, 60, 'board_rate_limit')
    }
    return { db, isAdmin, session: session! }
}
export async function listPosts(context: BoardContext, params: URLSearchParams) {
    const parsed = z.object({ q: z.string().trim().max(100), category: z.enum(['all', 'general', 'notice', 'resources']), page: z.coerce.number().int().min(1).max(5000), manage: z.enum(['0', '1']) }).safeParse({
        q: params.get('q') || '', category: params.get('category') || 'all', page: params.get('page') || 1, manage: params.get('manage') || '0',
    })
    if (!parsed.success) throw new AdminError(400, 'invalid_request')
    const { q, category, page, manage } = parsed.data
    if (manage === '1' && !context.isAdmin) throw new AdminError(403, 'forbidden')
    let query = context.db.from('board_posts').select(LIST_COLUMNS, { count: 'exact' })
    if (manage === '0') query = query.eq('status', 'published')
    if (category !== 'all') query = query.eq('category', category)
    // Quote the PostgREST values and escape LIKE wildcard characters rather than accepting filter syntax.
    if (q) {
        const pattern = `"%${q.replace(/[\\%_"]/g, character => `\\${character}`)}%"`
        query = query.or(`title.ilike.${pattern},body.ilike.${pattern}`)
    }
    const { data, error, count } = await query.order('is_pinned', { ascending: false }).order('published_at', { ascending: false, nullsFirst: false }).order('id', { ascending: false }).range((page - 1) * BOARD_PAGE_SIZE, page * BOARD_PAGE_SIZE - 1)
    if (error) throw new AdminError(503, 'not_configured')
    return { posts: (data || []).map(post => publicPost(post as unknown as StoredPost)), total: count || 0, page, isAdmin: context.isAdmin }
}
export async function readPost(context: BoardContext, id: string, includePrivate = false): Promise<StoredPost> {
    let query = context.db.from('board_posts').select(includePrivate ? `${PUBLIC_COLUMNS},password_hash` : PUBLIC_COLUMNS).eq('id', validId(id))
    if (!includePrivate && !context.isAdmin) query = query.eq('status', 'published')
    const { data, error } = await query.maybeSingle()
    if (error) throw new AdminError(503, 'request_failed')
    if (!data) throw new AdminError(404, 'not_found')
    return data as unknown as StoredPost
}
export async function authorizePost(context: BoardContext, id: string, password: string) {
    validId(id)
    if (!context.isAdmin) {
        if (!passwordSchema.safeParse(password).success) throw new AdminError(403, 'invalid_password')
        await adminRateLimit(context.db, 'board-password', id, 10, 900, 'board_rate_limit')
    }
    const post = await readPost(context, id, true)
    if (!context.isAdmin && !await verifyBoardPassword(password, post.password_hash)) throw new AdminError(403, 'invalid_password')
    return post
}

type Upload = { name: string; mime: string; bytes: Uint8Array }
export async function parsePostForm(request: Request): Promise<{ input: PostInput; files: Upload[] }> {
    const contentType = request.headers.get('content-type') || ''
    if (!contentType.startsWith('multipart/form-data;')) throw new AdminError(400, 'invalid_request')
    const raw = await boundedBody(request, MAX_ATTACHMENT_BYTES + 128 * 1024)
    let form: FormData
    try { form = await new Response(Buffer.from(raw), { headers: { 'Content-Type': contentType } }).formData() }
    catch { throw new AdminError(400, 'invalid_request') }
    let payload: unknown
    try { payload = JSON.parse(String(form.get('payload'))) } catch { throw new AdminError(400, 'invalid_request') }
    const parsed = postSchema.safeParse(payload)
    if (!parsed.success) throw new AdminError(400, 'invalid_request')
    const entries = form.getAll('files')
    if (entries.length > MAX_ATTACHMENTS) throw new AdminError(413, 'too_large')
    const files: Upload[] = []
    for (const entry of entries) {
        if (typeof entry === 'string' || entry.size === 0) throw new AdminError(400, 'invalid_file')
        if (entry.size > MAX_ATTACHMENT_BYTES) throw new AdminError(413, 'too_large')
        const bytes = new Uint8Array(await entry.arrayBuffer())
        const name = entry.name.replace(/[\x00-\x1f\x7f/\\]/g, '_').slice(0, 160)
        files.push({ name, bytes, mime: fileMime(name, bytes) })
    }
    return { input: parsed.data, files }
}
export function fileMime(name: string, bytes: Uint8Array) {
    const ext = name.split('.').pop()?.toLowerCase()
    const pdf = Buffer.from(bytes.subarray(0, 5)).toString() === '%PDF-'
    const ole = Buffer.from(bytes.subarray(0, 8)).equals(Buffer.from('d0cf11e0a1b11ae1', 'hex'))
    const zip = bytes[0] === 0x50 && bytes[1] === 0x4b && bytes[2] === 3 && bytes[3] === 4
    if (ext === 'pdf' && pdf) return 'application/pdf'
    if (ext === 'hwp' && ole || ext === 'hwpx' && zip) return 'application/octet-stream'
    if (ext === 'doc' && ole) return 'application/msword'
    if (ext === 'xls' && ole) return 'application/vnd.ms-excel'
    if (ext === 'docx' && zip) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if (ext === 'xlsx' && zip) return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    throw new AdminError(400, 'invalid_file')
}
async function removeFiles(context: BoardContext, files: StoredAttachment[]) {
    if (!files.length) return
    // A failed cleanup leaves inaccessible private objects, not downloadable attachments.
    try { await context.db.storage.from(BOARD_BUCKET).remove(files.map(file => file.path)) } catch { /* See the orphan cleanup runbook. */ }
}
export async function savePost(context: BoardContext, input: PostInput, files: Upload[], id?: string) {
    const previous = id ? await authorizePost(context, id, input.password) : null
    if (!previous && !passwordSchema.safeParse(input.password).success) throw new AdminError(400, 'invalid_request')
    if (previous && previous.revision !== input.revision) throw new AdminError(409, 'conflict')
    if (!context.isAdmin && ((input.category === 'notice' && previous?.category !== 'notice') || input.is_pinned !== (previous?.is_pinned || false))) throw new AdminError(403, 'forbidden')
    if (new Set(input.keepAttachmentIds).size !== input.keepAttachmentIds.length) throw new AdminError(400, 'invalid_request')
    const kept = (previous?.attachments || []).filter(file => input.keepAttachmentIds.includes(file.id))
    if (kept.length !== input.keepAttachmentIds.length) throw new AdminError(400, 'invalid_request')
    if (kept.length + files.length > MAX_ATTACHMENTS || kept.reduce((sum, file) => sum + file.size, 0) + files.reduce((sum, file) => sum + file.bytes.length, 0) > MAX_ATTACHMENT_BYTES) throw new AdminError(413, 'too_large')
    const postId = previous?.id || randomUUID()
    const uploaded: StoredAttachment[] = []
    for (const file of files) {
        const attachmentId = randomUUID()
        const path = `${postId}/${attachmentId}`
        const { error } = await context.db.storage.from(BOARD_BUCKET).upload(path, file.bytes, { contentType: file.mime, upsert: false })
        if (error) { await removeFiles(context, uploaded); throw new AdminError(503, 'request_failed') }
        uploaded.push({ id: attachmentId, path, name: file.name, size: file.bytes.length, mime: file.mime })
    }
    const now = new Date().toISOString()
    const record = {
        author_name: input.author_name, title: input.title, body: input.body, category: input.category,
        status: input.status, is_pinned: input.is_pinned, attachments: [...kept, ...uploaded],
        updated_at: now, published_at: input.status === 'published' ? previous?.published_at || now : null,
    }
    const result = previous
        ? await context.db.from('board_posts').update({ ...record, revision: previous.revision + 1 }).eq('id', postId).eq('revision', previous.revision).select(PUBLIC_COLUMNS).maybeSingle()
        : await context.db.from('board_posts').insert({ ...record, id: postId, password_hash: await hashBoardPassword(input.password) }).select(PUBLIC_COLUMNS).single()
    if (result.error) {
        // Commit outcome can be ambiguous after transport failure. Retain new private objects for recovery.
        throw new AdminError(503, 'request_failed')
    }
    if (!result.data) { await removeFiles(context, uploaded); throw new AdminError(409, 'conflict') }
    if (previous) await removeFiles(context, previous.attachments.filter(file => !input.keepAttachmentIds.includes(file.id)))
    return publicPost(result.data as StoredPost)
}
export async function deletePost(context: BoardContext, id: string, password: string, revision: number) {
    const post = await authorizePost(context, id, password)
    if (post.revision !== revision) throw new AdminError(409, 'conflict')
    const { data, error } = await context.db.from('board_posts').delete().eq('id', id).eq('revision', revision).select('id').maybeSingle()
    if (error) throw new AdminError(503, 'request_failed')
    if (!data) throw new AdminError(409, 'conflict')
    await removeFiles(context, post.attachments)
}
