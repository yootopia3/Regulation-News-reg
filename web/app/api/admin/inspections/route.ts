import type { NextRequest } from 'next/server'
import { z } from 'zod'
import { AdminError, requireAdmin, adminFailure, privateJson, boundedJson, adminRateLimit } from '@/lib/admin-auth'
import { PublicationReport } from '@/lib/publication'
import { checkPublication } from '@/lib/publication-service'

const RequestBody = z.object({ article_id: z.string().uuid(), request_id: z.string().uuid() }).strict()
const JOB_COLUMNS = 'id,article_id,status,error_code,updated_at'

export async function GET(request: NextRequest) {
    try {
        const { db } = await requireAdmin(request)
        const id = request.nextUrl.searchParams.get('id')
        if (id) {
            if (!z.string().uuid().safeParse(id).success) throw new AdminError(400, 'invalid_id')
            const { data, error } = await db.from('sanction_inspections').select(`${JOB_COLUMNS},result,review_revision,review_draft`).eq('id', id).maybeSingle()
            if (error) throw new AdminError(500, 'request_failed')
            if (!data) throw new AdminError(404, 'not_found')
            return privateJson({ job: data })
        }
        const [jobs, articles] = await Promise.all([
            db.from('sanction_inspections').select(JOB_COLUMNS).order('updated_at', { ascending: false }).limit(50),
            db.from('articles').select('id,title,published_at').eq('category', 'sanction_notice').in('agency', ['FSS_SANCTION', 'FSS_MGMT_NOTICE']).order('published_at', { ascending: false }).limit(100),
        ])
        if (jobs.error || articles.error) throw new AdminError(500, 'request_failed')
        return privateJson({ jobs: jobs.data, articles: articles.data, enabled: process.env.SANCTION_INSPECTIONS_ENABLED === 'true' })
    } catch (error) { return adminFailure(error) }
}

const ReviewAction = z.discriminatedUnion('action', [
    z.object({ action: z.literal('save'), id: z.string().uuid(), revision: z.number().int().nonnegative(), report: PublicationReport }).strict(),
    z.object({ action: z.literal('publish'), id: z.string().uuid(), revision: z.number().int().nonnegative(), reviewed: z.literal(true) }).strict(),
    z.object({ action: z.literal('withdraw'), id: z.string().uuid(), revision: z.number().int().nonnegative() }).strict(),
])
export async function PATCH(request: NextRequest) {
    try {
        const { db, userId } = await requireAdmin(request)
        const parsed = ReviewAction.safeParse(await boundedJson(request, 512*1024))
        if (!parsed.success) throw new AdminError(400, 'invalid_request')
        const input = parsed.data
        if (input.action === 'publish') {
            if (process.env.SANCTION_PUBLICATIONS_ENABLED !== 'true') throw new AdminError(503, 'disabled')
            await checkPublication(db, input.id, input.revision)
        }
        const { data, error } = await db.rpc('inspection_review_action', { p_id: input.id, p_actor: userId,
            p_revision: input.revision, p_action: input.action, p_report: input.action === 'save' ? input.report : null })
        if (error) throw new AdminError(409, 'review_conflict')
        return privateJson({ revision: data })
    } catch (error) { return adminFailure(error) }
}

export async function POST(request: NextRequest) {
    try {
        const { db, userId } = await requireAdmin(request)
        if (process.env.SANCTION_INSPECTIONS_ENABLED !== 'true') throw new AdminError(503, 'disabled')
        const parsed = RequestBody.safeParse(await boundedJson(request, 1024))
        if (!parsed.success) throw new AdminError(400, 'invalid_request')
        await adminRateLimit(db, 'inspection-run', userId, 10, 3600)
        const { data, error } = await db.rpc('inspection_enqueue', { p_article: parsed.data.article_id, p_actor: userId, p_request: parsed.data.request_id })
        if (error) throw new AdminError(409, ['no_active_documents', 'invalid_article'].includes(error.message) ? error.message : 'request_failed')
        return privateJson({ id: data }, 202)
    } catch (error) { return adminFailure(error) }
}
