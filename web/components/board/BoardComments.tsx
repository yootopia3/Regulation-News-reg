'use client'
import { boardDate } from '@/lib/board/client'
import { useBoardComments } from '@/lib/board/use-comments'
import { MAX_COMMENT_BODY_LENGTH } from '@/lib/board/types'

const field = 'mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm'
export default function BoardComments({ postId }: { postId: string }) {
    const comments = useBoardComments(postId)
    return <section aria-label="댓글" className="mt-6 rounded-xl border border-slate-200 bg-white p-5 sm:p-8">
        <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">댓글 {comments.total.toLocaleString()}</h2><span className="text-xs text-slate-500">최신순</span></div>
        {comments.loadError ? <div role="alert" className="mt-4 text-sm text-red-700"><p>{comments.loadError}</p><button type="button" onClick={() => comments.reload()} className="mt-2 underline">댓글 다시 불러오기</button></div>
            : comments.loading ? <p role="status" className="mt-4 text-sm text-slate-500">댓글을 불러오는 중입니다.</p>
                : !comments.comments.length ? <p className="mt-4 text-sm text-slate-500">첫 댓글을 남겨보세요.</p>
                    : <ul className="mt-4 divide-y divide-slate-100">{comments.comments.map(comment => <li key={comment.id} className="py-5">
                        <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><div><span className="font-medium">{comment.author_name}</span><span className="ml-3 text-xs text-slate-500">{boardDate(comment.created_at)}{comment.revision > 0 && ' · 수정됨'}</span></div>
                            <div className="flex gap-3"><button type="button" disabled={comments.busy} aria-label={`${comment.author_name} 댓글 수정`} onClick={() => comments.begin(comment, 'edit')} className="text-slate-600 underline">수정</button><button type="button" disabled={comments.busy} aria-label={`${comment.author_name} 댓글 삭제`} onClick={() => comments.begin(comment, 'delete')} className="text-red-700 underline">삭제</button></div></div>
                        <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{comment.body}</p>
                        {comments.action?.comment.id === comment.id && <form className="mt-4 rounded-lg bg-slate-50 p-4" onSubmit={event => { event.preventDefault(); void comments.confirm() }}>
                            <fieldset disabled={comments.busy} className="space-y-3">
                                {comments.action.kind === 'edit' ? <label className="block text-sm font-medium">수정할 댓글<textarea className={`${field} min-h-24`} maxLength={MAX_COMMENT_BODY_LENGTH} value={comments.editBody} onChange={event => comments.setEditBody(event.target.value)} required /></label>
                                    : <p className="text-sm text-red-700">이 댓글을 삭제할까요? 삭제 후에는 복구할 수 없습니다.</p>}
                                {!comments.isAdmin && <label className="block text-sm font-medium">댓글 확인 비밀번호<input className={field} type="password" autoComplete="off" minLength={8} maxLength={128} value={comments.actionPassword} onChange={event => comments.setActionPassword(event.target.value)} required /></label>}
                                <div className="flex gap-3"><button type="submit" className="rounded-lg bg-blue-900 px-4 py-2 text-sm text-white">{comments.busy ? '처리 중…' : comments.action.kind === 'edit' ? '수정 저장' : '댓글 삭제 확인'}</button><button type="button" onClick={comments.cancel} className="rounded-lg border px-4 py-2 text-sm">취소</button></div>
                            </fieldset>
                        </form>}
                    </li>)}</ul>}
        {comments.error && <p role="alert" className="mt-4 text-sm text-red-700">{comments.error}</p>}
        {comments.notice && <p role="status" className="mt-4 text-sm text-blue-800">{comments.notice}</p>}
        {!comments.loading && !comments.loadError && comments.totalPages > 1 && <nav aria-label="댓글 페이지" className="mt-4 flex items-center justify-center gap-4 text-sm">
            <button type="button" disabled={comments.page === 1 || comments.busy} onClick={() => comments.reload(comments.page - 1)} className="rounded border px-3 py-2 disabled:opacity-40">이전 댓글</button>
            <span>{comments.page} / {comments.totalPages}</span>
            <button type="button" disabled={comments.page === comments.totalPages || comments.busy} onClick={() => comments.reload(comments.page + 1)} className="rounded border px-3 py-2 disabled:opacity-40">다음 댓글</button>
        </nav>}
        <form className="mt-6 border-t border-slate-100 pt-5" onSubmit={event => { event.preventDefault(); void comments.create() }}>
            <fieldset disabled={comments.busy || comments.loading || !!comments.loadError} className="space-y-4">
                <legend className="text-sm font-semibold">댓글 작성</legend>
                <div className="grid gap-4 pt-3 sm:grid-cols-2"><label className="block text-sm font-medium">댓글 작성자 이름<input className={field} maxLength={40} value={comments.author} onChange={event => comments.setAuthor(event.target.value)} required /></label>
                    <label className="block text-sm font-medium">댓글 비밀번호<input className={field} type="password" autoComplete="new-password" minLength={8} maxLength={128} value={comments.password} onChange={event => comments.setPassword(event.target.value)} required /></label></div>
                <p className="text-xs text-slate-500">댓글 비밀번호는 8~128자이며 이 댓글의 수정·삭제에 사용합니다.</p>
                <label className="block text-sm font-medium">댓글 내용<textarea className={`${field} min-h-28`} maxLength={MAX_COMMENT_BODY_LENGTH} value={comments.body} onChange={event => comments.setBody(event.target.value)} required /></label>
                <div className="flex items-center justify-between gap-3"><span className="text-xs text-slate-400">{comments.body.length.toLocaleString()} / {MAX_COMMENT_BODY_LENGTH.toLocaleString()}</span><button type="submit" className="rounded-lg bg-blue-900 px-5 py-2.5 text-sm font-semibold text-white">{comments.busy ? '처리 중…' : '댓글 등록'}</button></div>
            </fieldset>
        </form>
    </section>
}
