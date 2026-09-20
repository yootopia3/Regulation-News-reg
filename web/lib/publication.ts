import { z } from 'zod'
import type { InspectionDraft } from './inspection-ui'

const Text = (max: number) => z.string().trim().min(1).max(max)
export const DutyBasis = z.enum(['explicit', 'inferred', 'limited'])
const DepartmentBasis = z.object({ department: Text(120), basis: DutyBasis,
    duty_ids: z.array(z.string().regex(/^HQ-[0-9]{3,5}$/)).min(1).max(2) }).strict()
export const ReportItem = z.object({
    finding_id: z.string().regex(/^F[1-9][0-9]?$/), title: Text(160), summary: Text(1000),
    departments: z.array(Text(120)).max(5), related_work: Text(500),
    source_pages: z.array(z.number().int().min(1).max(200)).min(1).max(5),
    department_basis: z.array(DepartmentBasis).max(5).optional(),
    checks: z.array(z.object({ question: Text(400), evidence_to_request: Text(300), department: Text(120).optional() }).strict()).min(1).max(30),
}).strict()
export const PublicationReport = z.object({ analysis_basis: z.enum(['organization', 'duty_master']).optional(),
    master_version: Text(80).optional(), master_fingerprint: z.string().regex(/^[0-9a-f]{64}$/).optional(),
    items: z.array(ReportItem).min(1).max(30) }).strict().superRefine((value, context) => {
    if (value.analysis_basis === 'duty_master') {
        if (!value.master_version || !value.master_fingerprint || value.items.some(i => !i.department_basis || i.checks.some(c => !c.department)))
            context.addIssue({ code: z.ZodIssueCode.custom, message: 'master_basis_required' })
    } else if (value.master_version || value.master_fingerprint || value.items.some(i => i.department_basis || i.checks.some(c => c.department))) {
        context.addIssue({ code: z.ZodIssueCode.custom, message: 'unexpected_master_basis' })
    }
})
export type PublicationReport = z.infer<typeof PublicationReport>
export type PublicationSource = { title: string; published_at: string; url: string | null }
export type PublishedReport = { id: string; article_id: string; published_at: string; report: PublicationReport; source: PublicationSource; publication_source?: 'manual' | 'automatic' }

// Editor seed is not approval; legacy drafts without related_work still require input.
export function initialReport(draft: InspectionDraft): PublicationReport {
    const master = draft.analysis_basis === 'duty_master'
    return { ...(draft.analysis_basis ? { analysis_basis: draft.analysis_basis } : {}),
        ...(master ? { master_version: draft.master_version, master_fingerprint: draft.master_fingerprint } : {}), items: draft.findings.map(f => {
        const matches = draft.matches.filter(m => m.finding_id === f.id)
        if (master && matches.some(m => !m.duty_basis || !m.duty_ids?.length)) throw new Error('master_basis_required')
        return { finding_id: f.id, title: f.title, summary: f.summary,
            departments: [...new Set(matches.map(m => m.department))], related_work: [...new Set(matches.map(m => m.related_work?.trim()).filter(Boolean))].join('; '),
            source_pages: [...new Set(f.evidence.map(e => e.page))],
            ...(master ? { department_basis: matches.map(m => ({ department: m.department, basis: m.duty_basis!, duty_ids: m.duty_ids! })) } : {}),
            checks: matches.length ? matches.flatMap(m => m.checks.map(c => ({ question: c.question, evidence_to_request: c.evidence_to_request,
                ...(master ? { department: m.department } : {}) }))) : [{ question: '', evidence_to_request: '' }],
        }
    }) }
}

export function publicReport(value: unknown): PublicationReport {
    const parsed = PublicationReport.parse(value)
    return { ...(parsed.analysis_basis ? { analysis_basis: parsed.analysis_basis } : {}),
        ...(parsed.analysis_basis === 'duty_master' ? { master_version: parsed.master_version, master_fingerprint: parsed.master_fingerprint } : {}), items: parsed.items.map(i => ({ finding_id: i.finding_id, title: i.title, summary: i.summary,
        departments: [...i.departments], related_work: i.related_work, source_pages: [...i.source_pages],
        ...(i.department_basis ? { department_basis: i.department_basis.map(b => ({ department: b.department, basis: b.basis, duty_ids: [...b.duty_ids] })) } : {}),
        checks: i.checks.map(c => ({ question: c.question, evidence_to_request: c.evidence_to_request, ...(c.department ? { department: c.department } : {}) })),
    })) }
}

export const ORGANIZATION_INFERENCE_NOTICE = '직제규정의 조직 목록을 기준으로 소관부서 후보·소관업무·점검포인트를 AI가 추정했습니다. 확정된 업무분장이 아니므로 담당자 확인이 필요합니다.'
export const DUTY_MASTER_NOTICE = '공시내규 기반 본부 업무원장을 참고한 예방 점검 제안입니다. 업무 근거 수준과 별개로, 해당 제재와의 관련성은 AI 추정이며 당행의 위반 사실을 뜻하지 않습니다. 영업조직은 대상에서 제외했습니다.'
export const DUTY_BASIS_LABELS = { explicit: '업무 근거 명시', inferred: '업무 귀속 추정', limited: '자료 부족 · 확인 필요' } as const
export function reportBasisNotice(report: PublicationReport) {
    return report.analysis_basis === 'duty_master' ? DUTY_MASTER_NOTICE : report.analysis_basis === 'organization' ? ORGANIZATION_INFERENCE_NOTICE : ''
}

export function withMasterDepartments(item: PublicationReport['items'][number], draft: InspectionDraft, names: string[]) {
    const matches = draft.matches.filter(m => m.finding_id === item.finding_id && names.includes(m.department))
    const departments = matches.map(m => m.department)
    return { ...item, departments,
        department_basis: matches.map(m => ({ department: m.department, basis: m.duty_basis!, duty_ids: m.duty_ids! })),
        checks: item.checks.filter(c => departments.includes(c.department || '')) }
}

export function newPublicationCheck(item: PublicationReport['items'][number], master: boolean) {
    return { question: '', evidence_to_request: '', ...(master ? { department: item.departments[0] || '' } : {}) }
}

const compact = (text: string) => text.normalize('NFKC').replace(/[\s\p{P}\p{Cf}]+/gu, '').toLowerCase()
export function validatePublication(report: PublicationReport, draft: InspectionDraft, privateTexts: string[]) {
    if (report.analysis_basis !== draft.analysis_basis) throw new Error('analysis_basis_mismatch')
    if (draft.analysis_basis === 'duty_master' && (report.master_version !== draft.master_version || report.master_fingerprint !== draft.master_fingerprint)) throw new Error('master_version_mismatch')
    const ids = report.items.map(i => i.finding_id)
    if (new Set(ids).size !== ids.length || ids.length !== draft.findings.length || draft.findings.some(f => !ids.includes(f.id))) throw new Error('finding_coverage_failed')
    for (const item of report.items) {
        const finding = draft.findings.find(f => f.id === item.finding_id)!
        if (draft.analysis_basis === 'organization' || draft.analysis_basis === 'duty_master') {
            const allowed = new Set(draft.matches.filter(m => m.finding_id === item.finding_id).map(m => m.department))
            if (item.departments.some(name => !allowed.has(name))) throw new Error('invalid_department')
        }
        if (draft.analysis_basis === 'duty_master') {
            const matches = draft.matches.filter(m => m.finding_id === item.finding_id)
            const basis = item.department_basis || []
            if (new Set(item.departments).size !== item.departments.length || basis.length !== item.departments.length ||
                new Set(basis.map(b => b.department)).size !== basis.length || basis.some(b => !item.departments.includes(b.department))) throw new Error('master_basis_mismatch')
            for (const b of basis) {
                const match = matches.find(m => m.department === b.department)
                if (!match || b.basis !== match.duty_basis || JSON.stringify([...b.duty_ids].sort()) !== JSON.stringify([...(match.duty_ids || [])].sort())) throw new Error('master_basis_mismatch')
            }
            if (item.checks.some(c => !c.department || !item.departments.includes(c.department))) throw new Error('invalid_department')
        }
        const pages = new Set(finding.evidence.map(e => e.page))
        if (item.source_pages.some(p => !pages.has(p))) throw new Error('invalid_public_evidence')
    }
    const fields = report.items.flatMap(i => [i.title, i.summary, ...(draft.analysis_basis ? [] : i.departments), i.related_work, ...i.checks.flatMap(c => [c.question, c.evidence_to_request])]).map(compact)
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
