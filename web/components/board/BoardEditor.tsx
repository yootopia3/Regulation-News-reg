'use client'
import Link from 'next/link'
import { useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { BOARD_CATEGORIES, BOARD_FILE_ACCEPT, type BoardCategory } from '@/lib/board/types'
import { useBoardEditor } from '@/lib/board/use-board'
import BoardBody from './BoardBody'
const field = 'mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 disabled:bg-slate-100'
export default function BoardEditor({ id }: { id?: string }) {
    const editor = useBoardEditor(id)
    const router = useRouter()
    const [preview, setPreview] = useState(false)
    const [confirmDelete, setConfirmDelete] = useState(false)
    const formRef = useRef<HTMLFormElement>(null)
    const bodyRef = useRef<HTMLTextAreaElement>(null)
    const alert = editor.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-800">{editor.error}</p>
    function insert(before: string, after = '') {
        const start = bodyRef.current?.selectionStart || 0
        const end = bodyRef.current?.selectionEnd || 0
        editor.setBody(editor.body.slice(0, start) + before + editor.body.slice(start, end) + after + editor.body.slice(end))
        bodyRef.current?.focus()
    }
    if (editor.saved) return <section className="rounded-xl border bg-white p-6 sm:p-8">
        <h1 className="text-xl font-bold">{editor.saved.status === 'published' ? '글이 게시되었습니다.' : '글이 임시저장되었습니다.'}</h1>
        <p className="mt-4 text-sm text-slate-600">아래 관리 링크를 즐겨찾기에 저장해주세요. 글 비밀번호로 수정·삭제할 수 있습니다. 임시저장 글은 목록에 표시되지 않습니다.</p>
        <a href={`/board/${editor.saved.id}/edit`} className="mt-5 block break-all text-blue-800 underline">글 관리 링크: /board/{editor.saved.id}/edit</a>
        <div className="mt-6 flex gap-4 text-sm">{editor.saved.status === 'published' && <Link className="rounded-lg bg-blue-900 px-4 py-2 text-white" href={`/board/${editor.saved.id}`}>게시글 보기</Link>}<Link href="/board" className="rounded-lg border px-4 py-2">목록으로</Link></div>
    </section>
    if (id && !editor.loaded) return <section className="max-w-lg rounded-xl border bg-white p-6 sm:p-8">
        <h1 className="text-xl font-bold">글 수정·삭제</h1><p className="mt-3 text-sm text-slate-600">작성할 때 설정한 글 비밀번호를 입력해주세요.</p>
        <form className="mt-5 space-y-4" onSubmit={event => { event.preventDefault(); void editor.unlock() }}>
            {!editor.isAdmin && <label className="block text-sm">글 비밀번호<input className={field} type="password" autoComplete="off" minLength={8} maxLength={128} value={editor.password} onChange={event => editor.setPassword(event.target.value)} required /></label>}
            {alert}<button disabled={editor.busy} className="rounded-lg bg-blue-900 px-5 py-2.5 text-white disabled:opacity-50">{editor.busy ? '확인 중…' : editor.isAdmin ? '관리자 권한으로 열기' : '확인'}</button>
        </form><p className="mt-5 text-xs text-slate-500">비밀번호를 잊으셨다면 관리자에게 수정·삭제를 요청해주세요.</p>
    </section>
    return <form ref={formRef} onSubmit={event => { event.preventDefault(); void editor.save('published') }} className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 sm:p-8">
        <h1 className="text-xl font-bold">{id ? '글 수정' : '새 글 작성'}</h1>
        {alert}
        <fieldset disabled={editor.busy || !editor.loaded} className="space-y-5 disabled:opacity-60">
            <div className="grid gap-5 sm:grid-cols-2"><label className="block text-sm font-medium">작성자 이름<input className={field} maxLength={40} value={editor.author} onChange={event => editor.setAuthor(event.target.value)} required /></label>
                <label className="block text-sm font-medium">분류<select className={field} value={editor.category} onChange={event => editor.setCategory(event.target.value as BoardCategory)}>{Object.entries(BOARD_CATEGORIES).filter(([key]) => key !== 'notice' || editor.isAdmin || editor.post?.category === 'notice').map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></div>
            <label className="block text-sm font-medium">제목<input className={field} maxLength={150} value={editor.title} onChange={event => editor.setTitle(event.target.value)} required /></label>
            <div><div className="mb-2 flex flex-wrap items-center gap-2 text-sm"><span className="mr-auto font-medium">본문</span><button type="button" onClick={() => setPreview(!preview)} className="rounded border px-3 py-1">{preview ? '편집으로' : '미리보기'}</button></div>
                <div className="mb-2 flex flex-wrap gap-2 text-xs"><button type="button" disabled={preview} className="rounded border px-3 py-1 font-bold" onClick={() => insert('**', '**')}>굵게</button><button type="button" disabled={preview} className="rounded border px-3 py-1" onClick={() => insert('\n- ')}>목록</button><button type="button" disabled={preview} className="rounded border px-3 py-1" onClick={() => insert('[', '](https://)')}>링크</button></div>
                {preview && <div className="min-h-64 rounded-lg border bg-slate-50 p-4"><BoardBody body={editor.body} /></div>}
                <textarea ref={bodyRef} aria-label="본문" className={`${field} min-h-72 ${preview ? 'sr-only' : ''}`} maxLength={20000} value={editor.body} onChange={event => editor.setBody(event.target.value)} required />
                <p className="mt-2 text-right text-xs text-slate-400">{editor.body.length.toLocaleString()} / 20,000</p>
            </div>
            <div><label className="block text-sm font-medium">첨부파일<input className={`${field} text-sm`} type="file" accept={BOARD_FILE_ACCEPT} multiple onChange={event => editor.setFiles(Array.from(event.target.files || []))} /></label>
                <p className="mt-2 text-xs text-slate-500">PDF·HWP·HWPX·Word·Excel, 최대 3개·합계 3MB</p>
                {editor.post?.attachments.map(file => <label key={file.id} className="mt-2 flex items-center gap-2 break-all text-sm"><input type="checkbox" checked={editor.keptIds.includes(file.id)} onChange={event => editor.setKeptIds(event.target.checked ? [...editor.keptIds, file.id] : editor.keptIds.filter(value => value !== file.id))} />기존 첨부 유지: {file.name}</label>)}
            </div>
            {!id && <label className="block text-sm font-medium">글 비밀번호<input className={field} type="password" autoComplete="new-password" minLength={8} maxLength={128} value={editor.password} onChange={event => editor.setPassword(event.target.value)} required /><span className="mt-2 block text-xs font-normal text-slate-500">8~128자. 이 글의 수정·삭제에 사용합니다. 다른 서비스의 비밀번호와 다르게 설정해주세요.</span></label>}
            {editor.isAdmin && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={editor.pinned} onChange={event => editor.setPinned(event.target.checked)} />중요 공지로 상단 고정</label>}
            <div className="flex flex-wrap gap-3 border-t pt-5">
                <button type="submit" className="rounded-lg bg-blue-900 px-5 py-2.5 text-sm font-semibold text-white">{editor.busy ? '처리 중…' : '게시하기'}</button>
                <button type="button" onClick={() => { if (formRef.current?.reportValidity()) void editor.save('draft') }} className="rounded-lg border px-5 py-2.5 text-sm">{editor.post?.status === 'published' ? '게시 취소·임시저장' : '임시저장'}</button>
                {id && <button type="button" onClick={() => setConfirmDelete(true)} className="ml-auto px-3 text-sm text-red-700">글 삭제</button>}
            </div>
            {confirmDelete && <div role="alert" className="rounded-lg bg-red-50 p-4 text-sm"><p>이 글과 첨부파일을 삭제할까요? 삭제 후에는 복구할 수 없습니다.</p><div className="mt-3 flex gap-4"><button type="button" onClick={() => void editor.remove(() => router.push('/board'))} className="font-semibold text-red-800">삭제 확인</button><button type="button" onClick={() => setConfirmDelete(false)}>취소</button></div></div>}
        </fieldset>
    </form>
}
