import type { SupabaseClient } from '@supabase/supabase-js'
import { AdminError } from './admin-auth'
import { publicReport, validatePublication, type PublishedReport } from './publication'
import { z } from 'zod'
import { publicSanctionUrl } from './sanction-report'

export async function checkPublication(db: SupabaseClient, id: string, revision: number) {
    const { data: job, error } = await db.from('sanction_inspections').select('result,review_draft,review_revision,versions,status').eq('id', id).maybeSingle()
    if (error) throw new AdminError(500, 'request_failed')
    if (!job || job.review_revision !== revision || job.status !== 'needs_review' || !job.result || !job.review_draft) throw new AdminError(409, 'review_conflict')
    const texts: string[] = []
    for (const documentId of Object.keys(job.versions)) {
        for (let offset = 0; ; offset += 1000) {
            const response = await db.from('internal_document_units').select('body').eq('document_id', documentId).order('article_key').range(offset, offset+999)
            if (response.error) throw new AdminError(500, 'request_failed')
            texts.push(...(response.data || []).map(row => row.body))
            if (!response.data || response.data.length < 1000) break
        }
        const meta = await db.from('internal_documents').select('title,object_key').eq('id', documentId).single()
        if (meta.error) throw new AdminError(500, 'request_failed')
        texts.push(meta.data.title, meta.data.object_key)
    }
    try { validatePublication(publicReport(job.review_draft), job.result, texts) }
    catch { throw new AdminError(400, 'publication_review_required') }
}

export async function publishedReports(db: SupabaseClient, offset = 0, id?: string, articleId?: string): Promise<PublishedReport[]> {
    let query = db.from('sanction_publications').select('inspection_id,article_id,published_at,report,articles(title,link,published_at)').eq('status', 'published')
    if (id) query = query.eq('inspection_id', id)
    if (articleId) query = query.eq('article_id', articleId)
    const { data, error } = await query.order('published_at', { ascending: false }).order('inspection_id').range(offset, offset+19)
    if (error) throw new AdminError(503, 'reports_unavailable')
    try {
        return (data || []).map(row => {
            const source = z.object({ title: z.string().min(1), link: z.string(), published_at: z.string() }).parse(row.articles)
            return { id: row.inspection_id, article_id: row.article_id, published_at: row.published_at,
                report: publicReport(row.report), source: { title: source.title, published_at: source.published_at, url: publicSanctionUrl(source.link) } }
        })
    } catch { throw new AdminError(503, 'reports_unavailable') }
}
