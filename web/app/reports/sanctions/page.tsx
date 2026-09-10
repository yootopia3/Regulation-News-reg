'use client'

import Link from 'next/link'
import { useState } from 'react'
import { sanctionAgencies, sanctionAgencyNames } from '@/components/dashboard/constants'
import { SANCTION_REPORT, filterSanctionSources, sanctionDate } from '@/lib/sanction-report'
import { useSanctionSources } from '@/hooks/useSanctionSources'
import PublishedInspections from '@/components/PublishedInspections'

export default function SanctionReportsPage() {
    const { rows, state, reload } = useSanctionSources()
    const [query, setQuery] = useState('')
    const [agency, setAgency] = useState('')
    const filtered = filterSanctionSources(rows, query, agency)
    return <main className="min-h-screen bg-slate-50 text-slate-900 px-5 py-8 md:p-12">
        <div className="max-w-5xl mx-auto">
            <nav aria-label="현재 위치" className="flex gap-3 text-sm text-blue-900"><Link href="/">대시보드</Link><span>/</span><span>Report</span><span>/</span><span aria-current="page">{SANCTION_REPORT.label}</span></nav>
            <header className="mt-8"><p className="text-sm font-semibold text-blue-700">Report</p><h1 className="text-3xl font-bold mt-2">{SANCTION_REPORT.label}</h1><p className="text-slate-600 mt-3">제재공시와 경영유의사항을 확인하고 유사 사고 예방을 위한 점검을 준비하세요.</p></header>
            <section aria-label="점검 리포트 안내" className="mt-7 rounded-2xl border border-blue-200 bg-blue-50 p-6">
                <h2 className="font-bold text-blue-950">제재사례를 사고예방 점검으로 연결하세요</h2>
                <p className="text-sm leading-6 text-blue-900 mt-2">게시된 점검 리포트에서 소관부서·관련 업무·점검 항목을 확인할 수 있습니다. 수집된 공시와 기존 요약도 아래에서 검색할 수 있습니다.</p>
                <Link href="/admin/documents" className="inline-block mt-3 text-sm font-semibold text-blue-900 underline underline-offset-4">관리자 문서 관리</Link>
                <Link href="/admin/inspections" className="inline-block mt-3 ml-5 text-sm font-semibold text-blue-900 underline underline-offset-4">관리자 분석 실행</Link>
            </section>
            <PublishedInspections />
            <section className="mt-9" aria-labelledby="sources-title">
                <div className="flex justify-between items-center gap-4"><h2 id="sources-title" className="text-xl font-bold">수집된 공시</h2><button onClick={reload} disabled={state === 'loading'} className="text-sm text-blue-800 disabled:opacity-50">새로고침</button></div>
                <p className="text-sm text-slate-500 mt-2">최신 수집 공시 최대 1,000건 범위에서 검색합니다.</p>
                <div className="grid gap-3 sm:grid-cols-[1fr_200px] mt-5">
                    <label className="text-sm font-medium">제목 검색<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="예: 토스뱅크" className="block w-full border border-slate-300 bg-white rounded-lg p-3 mt-2" /></label>
                    <label className="text-sm font-medium">공시 종류<select value={agency} onChange={event => setAgency(event.target.value)} className="block w-full border border-slate-300 bg-white rounded-lg p-3 mt-2"><option value="">전체</option>{sanctionAgencies.map(code => <option value={code} key={code}>{sanctionAgencyNames[code]}</option>)}</select></label>
                </div>
                {state === 'loading' && <p role="status" className="py-12 text-slate-500">공시를 불러오는 중입니다…</p>}
                {state === 'unauthorized' && <p role="alert" className="py-8">로그인이 만료되었습니다. <Link href="/login" className="text-blue-800 underline">다시 로그인</Link>해 주세요.</p>}
                {state === 'error' && <div role="alert" className="mt-6 p-5 rounded-xl bg-red-50 text-red-900">공시를 불러오지 못했습니다. <button onClick={reload} className="underline">다시 시도</button></div>}
                {state === 'ready' && <>
                    <p role="status" className="text-sm text-slate-500 mt-5">{filtered.length}건</p>
                    {!filtered.length && <p className="py-12 text-center text-slate-500">{rows.length ? '검색 조건에 맞는 공시가 없습니다.' : '수집된 제재공시가 없습니다.'}</p>}
                    <ul className="mt-4 space-y-4">{filtered.map(row => <li key={row.id} className="rounded-2xl border border-slate-200 bg-white p-6">
                        <div className="flex flex-wrap gap-3 items-center text-xs text-slate-500"><span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">{sanctionAgencyNames[row.agency]}</span><time dateTime={row.publishedAt}>{sanctionDate(row.publishedAt)}</time></div>
                        <h3 className="text-lg font-semibold mt-3">{row.title}</h3>
                        {row.summary.length > 0 ? <details className="mt-4 text-sm"><summary className="cursor-pointer text-blue-900">기존 수집 요약 보기</summary><ul className="list-disc pl-5 mt-3 space-y-2 leading-6 text-slate-700">{row.summary.map((line, index) => <li key={index}>{line}</li>)}</ul></details> : <p className="text-sm text-slate-500 mt-3">등록된 요약이 없습니다. 원문에서 내용을 확인해 주세요.</p>}
                        {row.originalUrl ? <a href={row.originalUrl} target="_blank" rel="noopener noreferrer" className="inline-block mt-4 text-sm font-semibold text-blue-800 underline underline-offset-4">금감원 원문 열기 ↗</a> : <p className="mt-4 text-sm text-slate-500">원문 링크 확인이 필요합니다.</p>}
                    </li>)}</ul>
                </>}
            </section>
        </div>
    </main>
}
