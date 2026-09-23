import type { PublicationReport } from '@/lib/publication'

export default function SanctionBriefing({ report }: { report: PublicationReport }) {
    return <div className="mt-6 space-y-8 text-slate-800">
        {report.items.map((item, itemIndex) => <article key={item.finding_id} aria-label={`지적사항 ${itemIndex + 1}: ${item.title}`} className="space-y-6 rounded-2xl border border-slate-200 p-4 sm:p-6">
            <h2 className="flex items-start gap-3 text-lg font-bold"><span className="shrink-0 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">지적사항 {itemIndex + 1}</span>{item.title}</h2>
            <section aria-label="제재공시 요약 브리핑">
                <h3 className="mb-4 flex items-center gap-3 text-base font-bold"><span className="rounded-lg bg-sky-50 px-2 py-1 text-xs text-sky-800">01</span>제재공시 요약 브리핑</h3>
                <p className="whitespace-pre-line break-keep rounded-r-xl border-l-4 border-sky-600 bg-slate-50 px-5 py-4 text-sm leading-7">{item.summary}</p>
            </section>
            <section aria-label="당행 관점 사고예방 점검" className="border-t border-slate-200 pt-6">
                <h3 className="mb-4 flex items-center gap-3 text-base font-bold"><span className="rounded-lg bg-sky-50 px-2 py-1 text-xs text-sky-800">02</span>당행 관점 사고예방 점검</h3>
                <dl className="grid grid-cols-[5rem_1fr] gap-x-3 gap-y-3 text-sm">
                    <dt className="font-semibold text-slate-500">소관부서</dt><dd><span className="font-bold text-sky-800">{item.departments.join(' · ') || '추가 검토 필요'}</span>
                        {(report.analysis_basis === 'organization' || report.analysis_basis === 'duty_master') && <span className="ml-2 inline-block text-xs text-slate-500">(직제규정 등 공시내규 기반 추정)</span>}
                        {item.department_basis?.some(b => b.basis === 'limited') && <p className="mt-1 text-xs text-amber-800">자료 부족 · 담당 확인 필요</p>}
                    </dd>
                    <dt className="font-semibold text-slate-500">소관업무</dt><dd className="whitespace-pre-line leading-7">{item.related_work}</dd>
                </dl>
            </section>
            <section aria-label="점검 포인트" className="border-t border-slate-200 pt-6">
                <h3 className="mb-4 flex items-center gap-3 text-base font-bold"><span className="rounded-lg bg-sky-50 px-2 py-1 text-xs text-sky-800">03</span>점검 포인트</h3>
                <ol className="space-y-3">{item.checks.map((check, index) => <li key={index} className="flex gap-3 rounded-xl border border-slate-200 p-4">
                    <span aria-hidden="true" className="text-sm font-bold text-sky-800">{String(index + 1).padStart(2, '0')}</span>
                    <div>{item.departments.length > 1 && check.department && <p className="mb-1 text-xs font-semibold text-sky-800">{check.department}</p>}
                        <p className="break-keep text-sm font-semibold leading-7">{check.question}</p>
                        <p className="mt-2 text-xs leading-6 text-slate-500"><strong className="mr-2 text-slate-600">점검자료 예시</strong>{check.evidence_to_request}</p>
                    </div>
                </li>)}</ol>
            </section>
        </article>)}
    </div>
}
