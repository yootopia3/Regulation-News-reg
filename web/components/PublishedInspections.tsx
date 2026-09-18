'use client'
import { ORGANIZATION_INFERENCE_NOTICE } from '@/lib/publication'
import { useState } from 'react'
import type { PublishedReport } from '@/lib/publication'

export default function PublishedInspections() {
    const [reports, setReports] = useState<PublishedReport[]>([])
    const [next, setNext] = useState<number | null>(null)
    const [state, setState] = useState<'idle'|'loading'|'ready'|'disabled'|'error'>('idle')
    async function load(offset = 0) {
        setState('loading')
        try {
            const response = await fetch(`/api/sanction-publications?offset=${offset}`, { cache: 'no-store' })
            if (!response.ok) throw new Error()
            const data = await response.json()
            if (!Array.isArray(data.reports)) throw new Error()
            setReports(current => offset ? [...current, ...data.reports] : data.reports)
            setNext(data.nextOffset); setState(data.enabled ? 'ready' : 'disabled')
        } catch { setReports([]); setState('error') }
    }
    return <section className="mt-8 rounded-2xl border bg-white p-6" aria-label="게시된 점검 리포트">
        <div className="flex justify-between gap-3"><h2 className="text-xl font-bold">게시된 점검 리포트</h2><button onClick={() => load()} disabled={state === 'loading'} className="text-blue-900 disabled:opacity-40">{state === 'idle' ? '리포트 조회' : '리포트 새로고침'}</button></div>
        <p className="text-sm text-slate-500 mt-2">소관부서·관련 업무·사고예방 점검표입니다. AI 자동 분석 결과는 담당자 확인이 필요합니다.</p>
        {state === 'loading' && <p role="status" className="mt-4">리포트를 불러오는 중입니다…</p>}
        {state === 'disabled' && <p className="mt-4">리포트 게시 기능을 준비하고 있습니다.</p>}
        {state === 'error' && <p role="alert" className="mt-4 text-red-800">리포트를 불러오지 못했습니다. 로그인 상태를 확인하고 다시 조회해 주세요.</p>}
        {state === 'ready' && !reports.length && <p className="mt-4 text-slate-500">게시된 리포트가 없습니다.</p>}
        {state === 'ready' && reports.map(report => <article key={report.id} className="border-t mt-5 pt-5">
            {report.report.analysis_basis === 'organization' && <p className="my-3 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">{ORGANIZATION_INFERENCE_NOTICE}</p>}
                    {report.publication_source === 'automatic' && <p className="text-sm text-amber-800">AI 자동 분석 · 담당자 확인 필요</p>}
            <h3 className="text-lg font-bold mb-2">{report.source.title}</h3>
            {report.source.url && <a href={report.source.url} target="_blank" rel="noopener noreferrer" className="inline-block mb-3 text-sm text-blue-900 underline">금감원 공시 원문 열기</a>}
            <div className="flex justify-between gap-3"><p className="text-sm text-slate-500">게시일 {new Date(report.published_at).toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul' })}</p><a href={`/api/sanction-publications?id=${encodeURIComponent(report.id)}&format=xlsx`} className="text-sm text-blue-900 underline">점검표 Excel 다운로드</a></div>
            {report.report.items.map(item => <div key={item.finding_id} className="mt-5"><h3 className="font-bold">{item.title}</h3><p className="mt-2">{item.summary}</p><p className="text-sm mt-3"><strong>소관부서</strong> {item.departments.join(', ') || '검토 필요'}</p><p className="text-sm mt-2"><strong>관련 업무</strong> {item.related_work}</p><ul className="list-disc pl-5 mt-3 space-y-2">{item.checks.map((c, i) => <li key={i}>{c.question}<p className="text-sm text-slate-500">요청 증빙: {c.evidence_to_request}</p></li>)}</ul><p className="text-xs mt-3 text-slate-500">공개 PDF {item.source_pages.join(', ')}쪽</p></div>)}
        </article>)}
        {state === 'ready' && next !== null && <button onClick={() => load(next)} className="mt-5 border rounded px-4 py-2">리포트 더 보기</button>}
    </section>
}
