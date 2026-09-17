import { z } from 'zod'
import type { InspectionDraft } from './inspection-ui'

const Text = (max: number) => z.string().trim().min(1).max(max)
export const ReportItem = z.object({
    finding_id: z.string().regex(/^F[1-9][0-9]?$/), title: Text(160), summary: Text(1000),
    departments: z.array(Text(120)).max(5), related_work: Text(500),
    source_pages: z.array(z.number().int().min(1).max(200)).min(1).max(5),
    checks: z.array(z.object({ question: Text(400), evidence_to_request: Text(300) }).strict()).min(1).max(30),
}).strict()
export const PublicationReport = z.object({ items: z.array(ReportItem).min(1).max(30) }).strict()
export type PublicationReport = z.infer<typeof PublicationReport>
export type PublicationSource = { title: string; published_at: string; url: string | null }
export type PublishedReport = { id: string; article_id: string; published_at: string; report: PublicationReport; source: PublicationSource; publication_source?: 'manual' | 'automatic' }

// Editor seed is not approval; legacy drafts without related_work still require input.
export function initialReport(draft: InspectionDraft): PublicationReport {
    return { items: draft.findings.map(f => {
        const matches = draft.matches.filter(m => m.finding_id === f.id)
        return { finding_id: f.id, title: f.title, summary: f.summary,
            departments: [...new Set(matches.map(m => m.department))], related_work: [...new Set(matches.map(m => m.related_work?.trim()).filter(Boolean))].join('; '),
            source_pages: [...new Set(f.evidence.map(e => e.page))],
            checks: matches.length ? matches.flatMap(m => m.checks).map(c => ({ question: c.question, evidence_to_request: c.evidence_to_request })) : [{ question: '', evidence_to_request: '' }],
        }
    }) }
}

export function publicReport(value: unknown): PublicationReport {
    const parsed = PublicationReport.parse(value)
    return { items: parsed.items.map(i => ({ finding_id: i.finding_id, title: i.title, summary: i.summary,
        departments: [...i.departments], related_work: i.related_work, source_pages: [...i.source_pages],
        checks: i.checks.map(c => ({ question: c.question, evidence_to_request: c.evidence_to_request })),
    })) }
}

const compact = (text: string) => text.normalize('NFKC').replace(/[\s\p{P}\p{Cf}]+/gu, '').toLowerCase()
export function validatePublication(report: PublicationReport, draft: InspectionDraft, privateTexts: string[]) {
    const ids = report.items.map(i => i.finding_id)
    if (new Set(ids).size !== ids.length || ids.length !== draft.findings.length || draft.findings.some(f => !ids.includes(f.id))) throw new Error('finding_coverage_failed')
    for (const item of report.items) {
        const finding = draft.findings.find(f => f.id === item.finding_id)!
        const pages = new Set(finding.evidence.map(e => e.page))
        if (item.source_pages.some(p => !pages.has(p))) throw new Error('invalid_public_evidence')
    }
    const fields = report.items.flatMap(i => [i.title, i.summary, ...i.departments, i.related_work, ...i.checks.flatMap(c => [c.question, c.evidence_to_request])]).map(compact)
    // Check concatenated fields too, so splitting a quote across fields cannot bypass detection.
    const output = fields.join('')
    const windows = new Set(Array.from({ length: Math.max(0, output.length-23) }, (_, i) => output.slice(i, i+24)))
    const quotes = draft.matches.flatMap(m => m.evidence.map(e => compact(e.quote))).filter(q => q.length >= 8)
    if (quotes.some(q => output.includes(q))) throw new Error('private_content_detected')
    if (quotes.some(q => {
        let remaining = q
        for (const field of fields.filter(f => f.length >= 4)) remaining = remaining.replace(field, '')
        return remaining.length === 0
    })) throw new Error('private_content_detected')
    for (const text of privateTexts.map(compact)) {
        if (text.length >= 8 && text.length < 24 && output.includes(text)) throw new Error('private_content_detected')
        for (let i = 0; i + 24 <= text.length; i++) {
            if (windows.has(text.slice(i, i+24))) throw new Error('private_content_detected')
        }
    }
}
