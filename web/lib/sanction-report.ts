import { sanctionAgencies } from '@/components/dashboard/constants'

export const SANCTION_REPORT = {
    label: '재제공시 리포트',
    path: '/reports/sanctions',
    category: 'sanction_notice',
} as const

export type SanctionSource = {
    id: string
    title: string
    agency: string
    publishedAt: string
    originalUrl: string | null
    summary: string[]
}

function record(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
}

// These are public FSS links only. Never turn an arbitrary DB value into a link.
export function publicSanctionUrl(value: unknown): string | null {
    if (typeof value !== 'string') return null
    try {
        const url = new URL(value)
        if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.port) return null
        if (url.hostname !== 'fss.or.kr' && url.hostname !== 'www.fss.or.kr') return null
        return url.href
    } catch { return null }
}

export function sanctionSources(payload: unknown): SanctionSource[] {
    if (!record(payload) || !Array.isArray(payload.articles)) throw new Error('invalid_response')
    const sources = new Map<string, SanctionSource>()
    for (const row of payload.articles) {
        if (!record(row) || row.category !== SANCTION_REPORT.category ||
            !sanctionAgencies.some(agency => agency === row.agency) ||
            typeof row.id !== 'string' || typeof row.title !== 'string' ||
            typeof row.published_at !== 'string' || !Number.isFinite(Date.parse(row.published_at))) continue
        const analysis = record(row.analysis_result) ? row.analysis_result : null
        sources.set(row.id, {
            id: row.id,
            title: row.title,
            agency: row.agency as string,
            publishedAt: row.published_at,
            originalUrl: publicSanctionUrl(row.link),
            summary: Array.isArray(analysis?.summary)
                ? analysis.summary.filter((line): line is string => typeof line === 'string') : [],
        })
    }
    return [...sources.values()].sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt))
}

export function filterSanctionSources(rows: SanctionSource[], query: string, agency: string) {
    const term = query.trim().toLocaleLowerCase('ko-KR')
    return rows.filter(row => (!agency || row.agency === agency) &&
        (!term || row.title.toLocaleLowerCase('ko-KR').includes(term)))
}

export function sanctionDate(value: string) {
    return new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value))
}
