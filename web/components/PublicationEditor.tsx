'use client'
import { useState } from 'react'
import { initialReport, type PublicationReport } from '@/lib/publication'
import type { InspectionJob } from '@/lib/inspection-ui'
import { documentRequest } from '@/lib/document-ui'

export default function PublicationEditor({ job }: { job: InspectionJob }) {
    const [report, setReport] = useState<PublicationReport>(() => job.review_draft || initialReport(job.result!))
    const [revision, setRevision] = useState(job.review_revision || 0)
    const [departmentText, setDepartmentText] = useState(() => report.items.map(item => item.departments.join(', ')))
    const [saved, setSaved] = useState(Boolean(job.review_draft))
    const [reviewed, setReviewed] = useState(false)
    const [busy, setBusy] = useState(false)
    const [message, setMessage] = useState('')
    const [error, setError] = useState('')
    function edit(index: number, value: Partial<PublicationReport['items'][number]>) {
        setReport(current => ({ items: current.items.map((item, i) => i === index ? { ...item, ...value } : item) }))
        setSaved(false); setReviewed(false); setMessage('')
    }
    async function action(action: 'save' | 'publish' | 'withdraw') {
        setBusy(true); setError(''); setMessage('')
        try {
            const body = { action, id: job.id, revision, ...(action === 'save' ? { report } : action === 'publish' ? { reviewed: true } : {}) }
            const result = await documentRequest('/api/admin/inspections', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
            setRevision(result.revision); if (action === 'save') setSaved(true); setReviewed(false)
            setMessage(action === 'save' ? '검토본을 저장했습니다. 기존 게시본이 있다면 철회됩니다.' : action === 'publish' ? '검토본을 게시했습니다.' : '게시를 철회했습니다.')
        } catch (e) { setError((e as Error).message) }
        finally { setBusy(false) }
    }
    const input = 'block w-full border border-slate-300 rounded p-2 mt-1 bg-white'
    return <section className="mt-8 border-t pt-6"><h2 className="text-xl font-bold">공개용 검토본 편집</h2>
        <p className="text-sm text-slate-600 mt-2">전체 지적사항을 확인하고 관련 업무를 작성하세요. 내부규정 원문·인용·파일명은 공개용 문장에 넣지 마세요. 저장하면 기존 게시본이 철회됩니다.</p>
        <fieldset disabled={busy} className="disabled:opacity-60">{report.items.map((item, i) => <div key={item.finding_id} className="mt-6 border rounded-xl p-4 space-y-3">
            <h3 className="font-semibold">{item.finding_id} · 공개 원문 {item.source_pages.join(', ')}쪽</h3>
            <label className="block text-sm">지적사항 제목<input value={item.title} maxLength={160} onChange={e => edit(i, { title: e.target.value })} className={input} /></label>
            <label className="block text-sm">요약<textarea value={item.summary} maxLength={1000} onChange={e => edit(i, { summary: e.target.value })} className={input} /></label>
            <label className="block text-sm">소관부서 · 쉼표로 구분<input value={departmentText[i]} onChange={e => { setDepartmentText(current => current.map((text, n) => n === i ? e.target.value : text)); edit(i, { departments: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }) }} className={input} /></label>
            <label className="block text-sm">관련 업무<textarea value={item.related_work} maxLength={500} onChange={e => edit(i, { related_work: e.target.value })} className={input} /></label>
            {item.checks.map((check, n) => <div key={n} className="border-l-2 border-blue-200 pl-3 space-y-2">
                <label className="block text-sm">점검 질문 {n+1}<textarea value={check.question} maxLength={400} onChange={e => edit(i, { checks: item.checks.map((c, j) => j === n ? { ...c, question: e.target.value } : c) })} className={input} /></label>
                <label className="block text-sm">요청 증빙 {n+1}<input value={check.evidence_to_request} maxLength={300} onChange={e => edit(i, { checks: item.checks.map((c, j) => j === n ? { ...c, evidence_to_request: e.target.value } : c) })} className={input} /></label>
                <button type="button" className="text-sm text-red-800" onClick={() => edit(i, { checks: item.checks.filter((_, j) => j !== n) })}>점검 항목 삭제</button>
            </div>)}
            <button type="button" disabled={item.checks.length >= 30} className="text-sm text-blue-900 disabled:opacity-40" onClick={() => edit(i, { checks: [...item.checks, { question: '', evidence_to_request: '' }] })}>점검 항목 추가</button>
        </div>)}</fieldset>
        <label className="block text-sm mt-5"><input type="checkbox" checked={reviewed} disabled={!saved || busy} onChange={e => setReviewed(e.target.checked)} className="mr-2" />저장된 전체 지적사항·부서·점검 항목을 검토했으며 내부 문서 내용이 공개되지 않음을 확인했습니다.</label>
        {error && <p role="alert" className="text-red-800 mt-3">{error}</p>}{message && <p role="status" className="text-blue-900 mt-3">{message}</p>}
        <div className="flex gap-4 mt-4"><button disabled={busy} onClick={() => action('save')} className="border rounded px-4 py-2 disabled:opacity-40">검토본 저장</button><button disabled={busy || !saved || !reviewed} onClick={() => action('publish')} className="bg-blue-900 text-white rounded px-4 py-2 disabled:opacity-40">검토본 게시</button><button disabled={busy} onClick={() => action('withdraw')} className="text-red-800 px-4 py-2">게시 철회</button></div>
    </section>
}
