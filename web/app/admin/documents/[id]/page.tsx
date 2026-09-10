'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { DOCUMENT_STATUS, documentRequest } from '@/lib/document-ui'

type Unit = { article_key: string; heading: string; department: string; body: string; start_paragraph: number; end_paragraph: number; reviewed: boolean }
type Doc = { title: string; status: string; revision: number; warnings: string[]; warnings_acknowledged: boolean; error_code: string | null }
export default function DocumentReview({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params)
    const [doc, setDoc] = useState<Doc | null>(null)
    const [units, setUnits] = useState<Unit[]>([])
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)
    const [deleting, setDeleting] = useState(false)
    const [saved, setSaved] = useState(false)
    const [dirty, setDirty] = useState(false)
    async function load() {
        const data = await documentRequest(`/api/admin/documents/${id}`)
        setDoc(data.document); setUnits(data.units); setSaved(false); setDirty(false)
    }
    useEffect(() => { let alive = true; documentRequest(`/api/admin/documents/${id}`).then(data => { if (alive) { setDoc(data.document); setUnits(data.units) } }).catch(e => { if (alive) setError(e.message) }); return () => { alive = false } }, [id])
    async function action(kind: string) {
        if (!doc) return
        setBusy(true); setError(''); setSaved(false)
        try {
            const body = kind === 'review' ? { action: kind, revision: doc.revision, units: units.map(({ article_key, department, reviewed }) => ({ article_key, department, reviewed })), warnings_acknowledged: doc.warnings_acknowledged } : { action: kind, revision: doc.revision }
            await documentRequest(`/api/admin/documents/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
            await load(); setDeleting(false); setSaved(true)
        } catch (e) { setError((e as Error).message) }
        finally { setBusy(false) }
    }
    return <main className="min-h-screen bg-slate-50 text-slate-900 p-6 md:p-10"><div className="max-w-5xl mx-auto"><Link href="/admin/documents" className="text-blue-800">문서 목록</Link>
        <h1 className="text-3xl font-bold mt-4">{doc?.title || '문서 검토'}</h1>
        {error && <p role="alert" className="mt-4 bg-red-50 text-red-800 p-4 rounded-lg">{error}</p>}
        {saved && <p role="status" className="mt-4 text-blue-800">저장했습니다.</p>}
        {doc && <><div className="mt-4 flex gap-4 items-center"><span>{DOCUMENT_STATUS[doc.status]}</span><button onClick={() => { void load().catch(e => setError(e.message)) }} className="text-blue-800">새로고침</button></div>
            {doc.error_code && <p className="mt-3 text-red-800">문서를 처리하지 못했습니다. 파일 형식과 처리 서버 상태를 확인해주세요. ({doc.error_code})</p>}
            {doc.warnings.length > 0 && <section className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-4"><h2 className="font-bold">추출 확인 사항</h2><ul>{doc.warnings.map((warning, i) => <li key={i} className="whitespace-pre-wrap text-sm mt-2">{warning}</li>)}</ul></section>}
            <p className="mt-5 text-sm text-slate-600">각 조문의 부서명을 확인하세요. 공통 규정은 부서명을 비워둘 수 있습니다. 원문과 비교한 뒤 검토 완료를 선택해주세요.</p>
            {units.map((unit, i) => <section key={unit.article_key} className="mt-4 bg-white border rounded-xl p-5"><h2 className="font-bold">제{unit.article_key}조 · {unit.heading}</h2><p className="text-xs text-slate-500 mt-1">추출 문단 {unit.start_paragraph}–{unit.end_paragraph} (페이지 번호 아님)</p>
                <label className="block text-sm mt-3">소관부서 후보<input maxLength={120} disabled={doc.status !== 'review' || busy} value={unit.department} onChange={event => { setDirty(true); setUnits(old => old.map((u, j) => j === i ? { ...u, department: event.target.value, reviewed: false } : u)) }} className="block border rounded-lg p-2 mt-1 w-full" /></label>
                <pre className="whitespace-pre-wrap font-sans text-sm leading-7 mt-4 bg-slate-50 p-4 rounded-lg">{unit.body}</pre>
                <label className="flex gap-2 mt-3 text-sm"><input type="checkbox" disabled={doc.status !== 'review' || busy} checked={unit.reviewed} onChange={event => { setDirty(true); setUnits(old => old.map((u, j) => j === i ? { ...u, reviewed: event.target.checked } : u)) }} />이 조문의 부서와 업무를 확인했습니다.</label>
            </section>)}
            {doc.status === 'review' && <section className="sticky bottom-0 bg-white border rounded-xl p-4 mt-5 shadow-sm"><label className="flex gap-2 text-sm"><input type="checkbox" checked={doc.warnings_acknowledged} disabled={busy} onChange={event => { setDirty(true); setDoc({ ...doc, warnings_acknowledged: event.target.checked }) }} />미분류 구간과 추출 확인 사항을 원본과 대조했습니다.</label><div className="flex gap-3 mt-3"><button disabled={busy} onClick={() => action('review')} className="border rounded-lg p-2">검토 저장</button><button disabled={busy || dirty || !doc.warnings_acknowledged || units.some(unit => !unit.reviewed)} onClick={() => action('activate')} className="bg-blue-900 text-white rounded-lg p-2">저장된 검토로 활성화</button></div><p className="text-xs text-slate-500 mt-2">전체 조문 검토를 저장한 뒤 활성화할 수 있습니다. 같은 종류의 기존 활성 문서는 이전 버전으로 전환됩니다.</p></section>}
            {doc.status === 'failed' && <button disabled={busy} onClick={() => action('retry')} className="border rounded-lg p-3 mt-5">추출 다시 시도</button>}
            {!['processing', 'deleting', 'deleted'].includes(doc.status) && <section className="mt-8 border-t pt-4">{deleting ? <><p className="text-red-800">원본 파일과 추출 업무를 삭제합니다. 이 문서는 분석에 사용할 수 없게 됩니다. 삭제 이력은 남습니다.</p><div className="flex gap-4 mt-3"><button disabled={busy} onClick={() => action('delete')} className="text-red-800">삭제 요청 확정</button><button onClick={() => setDeleting(false)}>취소</button></div></> : <button onClick={() => setDeleting(true)} className="text-red-800">문서 삭제</button>}</section>}
        </>}
    </div></main>
}
