import type { SupabaseClient } from '@supabase/supabase-js'
import { AdminError } from './admin-auth'
import { initialReport, publicReport, validatePublication } from './publication'
import { privatePublicationTexts } from './publication-service'
import type { InspectionDraft } from './inspection-ui'

export async function autoPublish(db: SupabaseClient, id: string) {
    const { data: job, error } = await db.from('sanction_inspections')
        .select('status,automation_status,result,review_revision,review_draft,versions').eq('id', id).maybeSingle()
    if (error) throw new AdminError(503, 'request_failed')
    if (!job) throw new AdminError(404, 'not_found')
    if (job.automation_status !== 'pending' || job.status !== 'needs_review') return 'skipped'
    // Never touch an administrator's saved draft, including legacy jobs.
    if (job.review_draft) return 'skipped'
    let report
    try {
        const draft = job.result as InspectionDraft
        if (!draft || draft.unmatched_finding_ids.length || draft.findings.some(f => !draft.matches.some(m => m.finding_id === f.id))) throw new Error()
        if (draft.matches.some(m => !m.related_work?.trim() || !m.department.trim())) throw new Error()
        report = publicReport(initialReport(draft))
    } catch {
        const marked = await db.rpc('inspection_auto_attention', { p_id: id, p_revision: job.review_revision })
        if (marked.error) throw new AdminError(503, 'request_failed')
        return 'needs_attention'
    }
    const texts = await privatePublicationTexts(db, job.versions)
    try { validatePublication(report, job.result, texts) }
    catch {
        const marked = await db.rpc('inspection_auto_attention', { p_id: id, p_revision: job.review_revision })
        if (marked.error) throw new AdminError(503, 'request_failed')
        return 'needs_attention'
    }
    const saved = await db.rpc('inspection_auto_publish', { p_id: id, p_revision: job.review_revision, p_report: report })
    if (saved.error) throw new AdminError(409, 'review_conflict')
    return 'published'
}
