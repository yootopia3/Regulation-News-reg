import { createHash, randomUUID } from 'node:crypto'
import { z } from 'zod'
import { AdminError, boundedBody } from '@/lib/admin-auth'
import type { SupabaseClient } from '@supabase/supabase-js'

export const DOCUMENT_BUCKET = 'internal-documents'
export const MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
export const DOCUMENT_COLUMNS = 'id,title,document_kind,effective_date,status,revision,error_code,created_at'
export const DocumentId = z.string().uuid()
export const UnitEdit = z.object({ article_key: z.string().min(1).max(80), department: z.string().max(120), reviewed: z.boolean() }).strict()
export const DocumentAction = z.discriminatedUnion('action', [
    z.object({ action: z.literal('review'), revision: z.number().int().nonnegative(), units: z.array(UnitEdit).min(1).max(500), warnings_acknowledged: z.boolean() }).strict(),
    z.object({ action: z.literal('activate'), revision: z.number().int().nonnegative() }).strict(),
    z.object({ action: z.literal('delete'), revision: z.number().int().nonnegative() }).strict(),
    z.object({ action: z.literal('retry'), revision: z.number().int().nonnegative() }).strict(),
])

export async function uploadDocument(db: SupabaseClient, userId: string, request: Request) {
    const bytes = await boundedBody(request, MAX_DOCUMENT_BYTES + 65536)
    let form: FormData
    try { form = await new Response(bytes.buffer as ArrayBuffer, { headers: { 'Content-Type': request.headers.get('content-type') || '' } }).formData() }
    catch { throw new AdminError(400, 'invalid_upload') }
    const meta = z.object({ title: z.string().trim().min(1).max(120), document_kind: z.enum(['allocation', 'analysis']), effective_date: z.string().date() }).safeParse({
        title: form.get('title'), document_kind: form.get('document_kind'), effective_date: form.get('effective_date'),
    })
    const file = form.get('file')
    if (!meta.success || !file || typeof file === 'string' || !/\.hwp$/i.test(file.name)) throw new AdminError(400, 'invalid_upload')
    if (!file.size || file.size > MAX_DOCUMENT_BYTES) throw new AdminError(413, 'too_large')
    const data = Buffer.from(await file.arrayBuffer())
    if (!data.subarray(0, 8).equals(Buffer.from([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]))) throw new AdminError(400, 'invalid_hwp')
    const hash = createHash('sha256').update(data).digest('hex')
    const id = randomUUID()
    // Register before upload, so interrupted uploads are tracked and can be deleted.
    const { error: insertError } = await db.from('internal_documents').insert({ id, ...meta.data, sha256: hash, object_key: `${id}.hwp`, created_by: userId })
    if (insertError) throw new AdminError(insertError.code === '23505' ? 409 : 500, insertError.code === '23505' ? 'duplicate_document' : 'request_failed')
    const { error: uploadError } = await db.storage.from(DOCUMENT_BUCKET).upload(`${id}.hwp`, data, { contentType: 'application/octet-stream', upsert: false })
    if (uploadError) throw new AdminError(500, 'upload_failed')
    const { error } = await db.rpc('internal_document_enqueue', { p_id: id, p_actor: userId })
    if (error) {
        // The transaction may have committed despite a lost response. Keep the
        // tracked original for the queued worker or stale-upload cleanup.
        throw new AdminError(500, 'queue_failed')
    }
    return id
}

export async function getDocument(db: SupabaseClient, id: string) {
    const { data, error } = await db.from('internal_documents').select(`${DOCUMENT_COLUMNS},warnings,warnings_acknowledged`).eq('id', id).maybeSingle()
    if (error) throw new AdminError(500, 'request_failed')
    if (!data) throw new AdminError(404, 'not_found')
    const units: unknown[] = []
    for (let offset = 0; ; offset += 1000) {
        const result = await db.from('internal_document_units').select('article_key,heading,department,body,start_paragraph,end_paragraph,reviewed').eq('document_id', id).order('start_paragraph').range(offset, offset + 999)
        if (result.error) throw new AdminError(500, 'request_failed')
        units.push(...(result.data || []))
        if (!result.data || result.data.length < 1000) break
    }
    return { document: data, units }
}
