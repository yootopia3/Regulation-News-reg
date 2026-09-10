'use client'
import { useEffect, useState } from 'react'
import { z } from 'zod'
import { PublicationReport, type PublishedReport } from '@/lib/publication'
import { publicSanctionUrl } from '@/lib/sanction-report'

const ResponseReport = z.object({ id: z.string().uuid(), article_id: z.string().uuid(), published_at: z.string(), report: PublicationReport,
    source: z.object({ title: z.string(), published_at: z.string(), url: z.string().nullable() }),
})
type State = 'loading' | 'ready' | 'empty' | 'disabled' | 'unauthorized' | 'error'
export function useSanctionReport(articleId: string) {
    const [state, setState] = useState<State>('loading')
    const [report, setReport] = useState<PublishedReport | null>(null)
    const [attempt, setAttempt] = useState(0)
    useEffect(() => {
        let active = true
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), 20000)
        async function load() {
            try {
                const response = await fetch(`/api/sanction-publications?articleId=${encodeURIComponent(articleId)}`, { cache: 'no-store', signal: controller.signal })
                if (!active) return
                if (response.status === 401) { setState('unauthorized'); return }
                if (!response.ok) throw new Error()
                const data = await response.json()
                if (!active) return
                if (data.enabled === false) { setState('disabled'); return }
                if (data.enabled !== true || !Array.isArray(data.reports) || data.reports.length > 1) throw new Error()
                if (!data.reports.length) { setState('empty'); return }
                const parsed = ResponseReport.parse(data.reports[0])
                if (parsed.article_id !== articleId) throw new Error()
                parsed.source.url = publicSanctionUrl(parsed.source.url)
                setReport(parsed); setState('ready')
            } catch { if (active) setState('error') }
            finally { clearTimeout(timer) }
        }
        void load()
        return () => { active = false; controller.abort(); clearTimeout(timer) }
    }, [articleId, attempt])
    return { state, report, retry: () => { setReport(null); setState('loading'); setAttempt(value => value + 1) } }
}
