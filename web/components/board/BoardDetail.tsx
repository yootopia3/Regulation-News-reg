'use client'
import Link from 'next/link'
import { BOARD_CATEGORIES } from '@/lib/board/types'
import { boardDate } from '@/lib/board/client'
import { useBoardPost } from '@/lib/board/use-board'
import BoardBody from './BoardBody'
import BoardComments from './BoardComments'
export default function BoardDetail({ id }: { id: string }) {
    const { post, error } = useBoardPost(id)
    if (error) return <div role="alert" className="rounded-xl border bg-white p-6"><p>{error}</p><Link href={`/board/${id}/edit`} className="mt-4 inline-block text-blue-800 underline">비밀번호로 글 관리</Link></div>
    if (!post) return <p role="status">게시글을 불러오는 중입니다.</p>
    return <>
        <article className="rounded-xl border border-slate-200 bg-white p-5 sm:p-8">
            <div className="text-sm font-medium text-blue-800">{post.is_pinned && '고정 · '}{BOARD_CATEGORIES[post.category]}{post.status === 'draft' && ' · 비공개'}</div>
            <h1 className="mt-3 break-words text-2xl font-bold">{post.title}</h1>
            <p className="mt-3 border-b border-slate-100 pb-6 text-sm text-slate-500">{post.author_name} · {boardDate(post.published_at || post.created_at)}</p>
            <div className="py-7"><BoardBody body={post.body} /></div>
            {!!post.attachments.length && <section aria-label="첨부파일" className="rounded-lg bg-slate-50 p-4"><h2 className="mb-3 text-sm font-semibold">첨부파일</h2><ul className="space-y-2">{post.attachments.map(file => <li key={file.id}><a href={`/api/board/${id}/attachments/${file.id}`} className="break-all text-sm text-blue-800 underline">{file.name}</a><span className="ml-2 text-xs text-slate-500">{Math.ceil(file.size / 1024)} KB</span></li>)}</ul></section>}
        </article>
        {post.status === 'published' && <BoardComments key={id} postId={id} />}
        <div className="mt-5 flex justify-between text-sm"><Link href="/board" className="rounded-lg border bg-white px-4 py-2">목록으로</Link><Link href={`/board/${id}/edit`} className="rounded-lg bg-blue-900 px-4 py-2 text-white">수정·삭제</Link></div>
    </>
}
