'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { DOCUMENT_STATUS, documentRequest } from '@/lib/document-ui'

type DocumentRow = { id: string; title: string; effective_date: string; status: string; revision: number }
export default function DocumentsPage() {
    const [rows, setRows] = useState<DocumentRow[]>([])
    const [next, setNext] = useState<number | null>(null)
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)
    const [notice, setNotice] = useState('')
    async function load(offset = 0) {
        setError('')
        try { const data = await documentRequest(`/api/admin/documents?offset=${offset}`); setRows(old => offset ? [...old, ...data.documents] : data.documents); setNext(data.nextOffset) }
        catch (e) { setError((e as Error).message) }
    }
    useEffect(() => { void load() }, [])
    async function upload(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        const form = event.currentTarget
        const body = new FormData(form)
        setBusy(true); setError(''); setNotice('')
        try { await documentRequest('/api/admin/documents', { method: 'POST', body }); form.reset(); await load(); setNotice('등록했습니다. 추출이 끝나면 문서를 열어 검토해주세요.') }
        catch (e) { await load(); setError((e as Error).message) }
        finally { setBusy(false) }
    }
    return <main className="min-h-screen bg-slate-50 text-slate-900 p-6 md:p-10"><div className="max-w-5xl mx-auto">
        <header className="flex justify-between gap-4"><div><Link href="/" className="text-sm text-blue-800">대시보드</Link><h1 className="text-3xl font-bold mt-3">내부 문서 관리</h1><p className="text-slate-600 mt-2">문서 등록 후 부서와 업무를 검토하고 활성화하세요. 원문과 추출 내용은 관리자에게만 표시됩니다.</p></div>
            <button className="text-sm shrink-0 self-start" onClick={async () => { try { await documentRequest('/api/admin/logout', { method: 'POST' }); window.location.assign('/admin/login') } catch (e) { setError((e as Error).message) } }}>로그아웃</button></header>
        {error && <p role="alert" className="mt-5 p-4 bg-red-50 text-red-800 rounded-lg">{error}</p>}
        {notice && <p role="status" className="mt-5 p-4 bg-blue-50 text-blue-900 rounded-lg">{notice}</p>}
        <form onSubmit={upload} className="bg-white border rounded-2xl p-6 mt-8 grid md:grid-cols-2 gap-4">
            <h2 className="text-lg font-bold md:col-span-2">문서 등록</h2>
            <label className="text-sm">문서 제목<input name="title" required maxLength={120} className="block w-full border rounded-lg p-2 mt-1" /></label>
            <label className="text-sm">문서 종류<select name="document_kind" className="block w-full border rounded-lg p-2 mt-1"><option value="organization">직제규정 (AI 추정 기준)</option><option value="allocation">업무분장규정</option><option value="analysis">업무분석서</option></select></label>
            <label className="text-sm">시행일<input name="effective_date" type="date" required className="block w-full border rounded-lg p-2 mt-1" /></label>
            <label className="text-sm">HWP 파일 · 최대 2MB<input name="file" type="file" accept=".hwp,.HWP" required className="block w-full p-2 mt-1" /></label>
            <p className="text-sm text-slate-500 md:col-span-2">암호화된 문서와 HWPX는 현재 지원하지 않습니다. 이 단계에서는 외부 AI 분석을 실행하지 않습니다.</p>
            <button disabled={busy} className="bg-blue-900 text-white rounded-lg px-5 py-3 justify-self-start disabled:opacity-50">{busy ? '등록 중…' : '등록하고 추출하기'}</button>
        </form>
        <section className="mt-8"><div className="flex justify-between items-center"><h2 className="text-xl font-bold">등록 문서</h2><button onClick={() => load()} className="text-blue-800">새로고침</button></div>
            {!rows.length && <p className="py-8 text-slate-500">등록된 문서가 없습니다.</p>}
            <ul className="mt-4 space-y-3">{rows.map(row => <li key={row.id} className="bg-white border rounded-xl p-5 flex justify-between gap-4"><div><Link href={`/admin/documents/${row.id}`} className="font-semibold text-blue-900">{row.title}</Link><p className="text-sm text-slate-500 mt-1">시행일 {row.effective_date}</p></div><span className="text-sm">{DOCUMENT_STATUS[row.status] || '확인 필요'}</span></li>)}</ul>
            {next !== null && <button onClick={() => load(next)} className="mt-4 border rounded-lg px-4 py-2">더 보기</button>}
        </section>
    </div></main>
}
