'use client'
import { useEffect, useRef } from 'react'
import { X, Sparkles, ExternalLink, Download } from 'lucide-react'
import type { Article } from './dashboard/NewsCard'
import { sanctionAgencyNames } from './dashboard/constants'
import { useSanctionReport } from '@/hooks/useSanctionReport'
import { publicSanctionUrl } from '@/lib/sanction-report'

export default function SanctionReportModal({ article, onClose }: { article: Article; onClose: () => void }) {
    const { state, report, retry } = useSanctionReport(article.id)
    const dialog = useRef<HTMLDivElement>(null)
    const close = useRef<HTMLButtonElement>(null)
    const original = report?.source.url || publicSanctionUrl(article.link)
    useEffect(() => {
        const previous = document.activeElement as HTMLElement | null
        const overflow = document.body.style.overflow
        document.body.style.overflow = 'hidden'
        close.current?.focus()
        return () => { document.body.style.overflow = overflow; previous?.focus() }
    }, [])
    return <div className="fixed inset-0 z-[80] flex items-center justify-center p-3 sm:p-6">
        <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
        <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="sanction-report-title" className="relative flex flex-col w-full max-w-4xl max-h-[90dvh] rounded-2xl bg-white border border-slate-200 shadow-2xl overflow-hidden text-slate-900"
            onKeyDown={event => {
                if (event.key === 'Escape') onClose()
                if (event.key === 'Tab') {
                    const nodes = dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input,select,textarea,[tabindex="0"]')
                    if (!nodes?.length) return
                    const first = nodes[0], last = nodes[nodes.length-1]
                    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
                    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
                }
            }}>
            <header className="flex items-center justify-between gap-4 px-5 py-4 sm:px-8 border-b border-slate-100">
                <div className="flex items-center gap-3"><span className="bg-blue-50 text-blue-600 p-2 rounded-xl"><Sparkles className="w-5 h-5" /></span><div><p className="text-sm font-bold">AI 심층 보고서</p><p className="text-xs text-slate-500 mt-1">제재공시 브리핑 · 당행 사고예방 점검</p></div></div>
                <button ref={close} onClick={onClose} aria-label="보고서 닫기" className="rounded-full p-2 text-slate-500 hover:bg-slate-100"><X className="w-5 h-5" /></button>
            </header>
            <div className="overflow-y-auto px-5 py-6 sm:px-8 sm:py-8">
                <div className="flex flex-wrap gap-2 text-xs font-semibold"><span className="bg-red-50 text-red-700 px-3 py-1 rounded-lg">{sanctionAgencyNames[article.agency]}</span>{state === 'ready' && <span className="bg-blue-50 text-blue-700 px-3 py-1 rounded-lg">{report?.publication_source === 'automatic' ? 'AI 자동 분석' : '관리자 검토 완료'}</span>}</div>
                <h1 id="sanction-report-title" className="text-2xl font-bold mt-3">{article.title}</h1>
                {state === 'loading' && <p role="status" className="py-14 text-center text-slate-500">제재공시 리포트를 불러오는 중입니다…</p>}
                {state === 'error' && <div role="alert" className="mt-6 bg-red-50 rounded-xl p-5 text-red-900">리포트를 불러오지 못했습니다. <button onClick={retry} className="underline font-semibold">다시 시도</button></div>}
                {state === 'unauthorized' && <p role="alert" className="mt-6">로그인이 만료되었습니다. <a href="/login" className="text-blue-800 underline">다시 로그인</a>해 주세요.</p>}
                {(state === 'empty' || state === 'disabled') && <>
                    <section className="mt-6 bg-slate-50 border border-slate-200 rounded-xl p-5"><h2 className="font-bold">제재공시 요약 브리핑</h2>
                        {article.analysis_result?.summary?.length ? <ul className="list-disc pl-5 mt-3 space-y-2 text-sm leading-6">{article.analysis_result.summary.map((text, i) => <li key={i}>{text}</li>)}</ul> : <p className="mt-3 text-sm text-slate-500">등록된 요약이 없습니다. 공시 원문에서 내용을 확인해 주세요.</p>}
                    </section><section className="mt-4 bg-blue-50 rounded-xl p-5"><h2 className="font-bold text-blue-950">당행 관점 점검</h2><p className="text-sm leading-6 text-blue-900 mt-2">{state === 'disabled' ? '당행 관점 리포트 제공을 준비하고 있습니다.' : '아직 게시된 당행 관점 리포트가 없습니다.'} 분석과 검증이 완료되면 소관부서·소관업무·점검 포인트를 확인할 수 있습니다.</p>{state === 'empty' && <button onClick={retry} className="mt-3 text-sm font-semibold text-blue-700 underline">분석 결과 새로고침</button>}</section>
                </>}
                {state === 'ready' && report && <>
                    {report.publication_source === 'automatic' && <p className="mb-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">AI 자동 분석 · 담당자 확인 필요</p>}
                    <section className="mt-6 bg-slate-50 border border-slate-200 rounded-2xl p-5 sm:p-6"><h2 className="text-lg font-bold">제재공시 요약 브리핑</h2><ol className="mt-4 space-y-4">{report.report.items.map((item, index) => <li key={item.finding_id}><h3 className="font-semibold">{index+1}. {item.title}</h3><p className="text-sm leading-7 text-slate-600 mt-1 whitespace-pre-line">{item.summary}</p></li>)}</ol></section>
                    <h2 className="mt-8 text-lg font-bold">당행 관점 사고예방 점검</h2>
                    {report.report.items.map((item, index) => <section key={item.finding_id} className="mt-4 border border-slate-200 rounded-2xl overflow-hidden"><h3 className="bg-blue-50 px-5 py-4 font-semibold text-blue-950">{index+1}. {item.title}</h3><div className="p-5 space-y-5">
                        <dl className="grid gap-4 sm:grid-cols-2"><div><dt className="text-xs font-semibold text-slate-500 mb-2">소관부서</dt><dd className="font-semibold">{item.departments.join(' · ') || '추가 검토 필요'}</dd></div><div><dt className="text-xs font-semibold text-slate-500 mb-2">소관업무</dt><dd className="text-sm leading-6 whitespace-pre-line">{item.related_work}</dd></div></dl>
                        <div><h4 className="font-semibold mb-3">점검 포인트</h4><ul className="space-y-3">{item.checks.map((check, i) => <li key={i} className="rounded-xl bg-slate-50 p-4"><p className="text-sm font-medium leading-6">{i+1}. {check.question}</p><p className="text-xs text-slate-500 mt-2 leading-5">확인할 증빙: {check.evidence_to_request}</p></li>)}</ul></div><p className="text-xs text-slate-400">공시 원문 {item.source_pages.join(', ')}쪽</p>
                    </div></section>)}
                </>}
            </div>
            <footer className="flex flex-wrap gap-3 px-5 py-4 sm:px-8 border-t border-slate-100 bg-white">
                {original && <a href={original} target="_blank" rel="noopener noreferrer" className="flex gap-2 items-center text-sm font-semibold border border-slate-200 rounded-xl px-4 py-3"><ExternalLink className="w-4 h-4" />공시 원문 보기</a>}
                {state === 'ready' && report && <a href={`/api/sanction-publications?id=${encodeURIComponent(report.id)}&format=xlsx`} className="flex gap-2 items-center text-sm font-semibold bg-blue-50 text-blue-700 rounded-xl px-4 py-3"><Download className="w-4 h-4" />점검표 Excel</a>}
            </footer>
        </div>
    </div>
}
