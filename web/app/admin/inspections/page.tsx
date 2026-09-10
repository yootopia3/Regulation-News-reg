'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import PublicationEditor from '@/components/PublicationEditor'
import { documentRequest } from '@/lib/document-ui'
import { INSPECTION_ERRORS, INSPECTION_STATUS, type InspectionJob } from '@/lib/inspection-ui'

export default function InspectionsPage() {
    const [articles, setArticles] = useState<{ id: string; title: string }[]>([])
    const [jobs, setJobs] = useState<InspectionJob[]>([])
    const [selected, setSelected] = useState('')
    const [detail, setDetail] = useState<InspectionJob | null>(null)
    const [error, setError] = useState('')
    const [notice, setNotice] = useState('')
    const [enabled, setEnabled] = useState(false)
    const [busy, setBusy] = useState(false)
    async function load() {
        setError(''); setDetail(null)
        try { const data = await documentRequest('/api/admin/inspections'); setArticles(data.articles); setJobs(data.jobs); setEnabled(data.enabled) }
        catch (e) { setError((e as Error).message) }
    }
    useEffect(() => { void load() }, [])
    async function execute(articleId: string) {
        setBusy(true); setError(''); setNotice(''); setDetail(null)
        try { await documentRequest('/api/admin/inspections', { method: 'POST', body: JSON.stringify({ article_id: articleId, request_id: crypto.randomUUID() }), headers: { 'Content-Type': 'application/json' } }); await load(); setNotice('요청을 접수했습니다. worker 실행 후 새로고침으로 상태를 확인하세요.') }
        catch (e) { setError((e as Error).message) }
        finally { setBusy(false) }
    }
    return <main className="min-h-screen bg-slate-50 text-slate-900 p-6 md:p-10"><div className="max-w-5xl mx-auto">
        <nav className="flex gap-5 text-sm text-blue-900"><Link href="/reports/sanctions">재제공시 리포트</Link><Link href="/admin/documents">내부 문서 관리</Link></nav>
        <h1 className="text-3xl font-bold mt-6">제재공시 분석 관리</h1><p className="mt-3 text-slate-600">활성 업무규정으로 부서와 점검 항목을 제안합니다. 아래 초안과 내부 근거는 관리자 전용이며 일반 사용자에게 게시되지 않습니다.</p>
        {error && <p role="alert" className="mt-5 text-red-800">{error}</p>}{notice && <p role="status" className="mt-5 text-blue-900">{notice}</p>}
        {!enabled && <p className="mt-5 text-amber-900">분석 실행이 비활성 상태입니다. 운영 설정을 확인해 주세요.</p>}
        <form onSubmit={e => { e.preventDefault(); void execute(selected) }} className="mt-6 p-5 bg-white border rounded-xl flex flex-wrap gap-4">
            <label className="flex-1 min-w-60">공시 선택 · 최신 100건<select required value={selected} onChange={e => setSelected(e.target.value)} className="block w-full border rounded p-3 mt-2"><option value="">공시를 선택하세요</option>{articles.map(a => <option key={a.id} value={a.id}>{a.title}</option>)}</select></label>
            <button disabled={!enabled || busy || !selected} className="bg-blue-900 text-white rounded px-5 py-3 self-end disabled:opacity-40">분석 실행</button>
        </form>
        <section className="mt-8"><div className="flex justify-between"><h2 className="text-xl font-bold">최근 작업 · 최대 50건</h2><button onClick={load} className="text-blue-900">새로고침</button></div>
            <ul className="mt-4 space-y-3">{jobs.map(job => <li key={job.id} className="p-5 bg-white border rounded-xl"><h3 className="font-semibold">{articles.find(a => a.id === job.article_id)?.title || job.article_id}</h3><p className="mt-2 text-sm">{INSPECTION_STATUS[job.status] || '확인 필요'}</p>
                {job.error_code && <p className="text-sm text-red-800 mt-2">{INSPECTION_ERRORS[job.error_code] || '분석을 완료하지 못했습니다. 설정과 원문을 확인해 주세요.'}</p>}
                {job.status === 'needs_review' && <button className="mt-3 text-blue-900 underline" onClick={async () => { setDetail(null); try { setDetail((await documentRequest(`/api/admin/inspections?id=${job.id}`)).job) } catch (e) { setError((e as Error).message) } }}>초안 확인</button>}
                {['failed', 'stale', 'needs_review'].includes(job.status) && <button disabled={busy || !enabled} className="mt-3 ml-4 text-blue-900 underline disabled:opacity-40" onClick={() => execute(job.article_id)}>다시 분석</button>}
            </li>)}</ul>
        </section>
        {detail?.status === 'needs_review' && detail.result && <section className="mt-8 border border-blue-200 bg-white rounded-xl p-6"><h2 className="text-xl font-bold">관리자 검토용 초안</h2><p className="text-sm mt-2 text-slate-500">아래 공개용 검토본을 저장·확인한 뒤 게시하세요.</p>
            {detail.result.findings.map(f => <article key={f.id} className="border-t mt-6 pt-5"><h3 className="font-bold">{f.title}</h3><p className="mt-2">{f.summary}</p>{f.evidence.map((e, i) => <p key={i} className="mt-2 text-sm text-slate-500">원문 {e.page}쪽: {e.quote}</p>)}
                {detail.result!.matches.filter(m => m.finding_id === f.id).map((m, i) => <div key={i} className="mt-4 bg-blue-50 p-4 rounded"><h4 className="font-semibold">후보 부서: {m.department}</h4><p className="mt-2">{m.rationale}</p><ul className="mt-3 space-y-2">{m.checks.map((c, n) => <li key={n}>{c.question}<p className="text-sm text-slate-600">요청 증빙: {c.evidence_to_request}</p></li>)}</ul><details className="mt-3 text-sm"><summary>내부 근거 · 관리자 전용</summary>{m.evidence.map((e, n) => <p key={n} className="mt-2">{e.ref}: {e.quote}</p>)}</details></div>)}
                {detail.result!.unmatched_finding_ids.includes(f.id) && <p className="mt-3 text-amber-900">담당 부서를 선정하지 못했습니다. 직접 검토가 필요합니다.</p>}
            </article>)}
            <PublicationEditor key={detail.id} job={detail} />
        </section>}
    </div></main>
}
