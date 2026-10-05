'use client'
import Link from 'next/link'
import { BOARD_CATEGORIES, BOARD_PAGE_SIZE } from '@/lib/board/types'
import { boardDate } from '@/lib/board/client'
import { useBoardList } from '@/lib/board/use-board'
import BoardAdminLogin from './BoardAdminLogin'
export default function BoardList() {
    const board = useBoardList()
    const pages = Math.max(1, Math.ceil(board.total / BOARD_PAGE_SIZE))
    return <>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap gap-2" aria-label="게시판 분류">
                {Object.entries({ all: '전체', ...BOARD_CATEGORIES }).map(([key, label]) => <button key={key} aria-pressed={board.category === key} onClick={() => board.selectCategory(key)} className={`rounded-full px-4 py-2 text-sm font-medium ${board.category === key ? 'bg-blue-900 text-white' : 'border border-slate-200 bg-white text-slate-600'}`}>{label}</button>)}
            </div>
            <Link href="/board/new" className="rounded-lg bg-blue-900 px-5 py-2.5 text-sm font-semibold text-white">글쓰기</Link>
        </div>
        <form role="search" onSubmit={event => { event.preventDefault(); board.searchPosts() }} className="mb-5 flex gap-2">
            <input aria-label="제목·본문 검색" placeholder="제목 또는 본문으로 검색" value={board.search} onChange={event => board.setSearch(event.target.value)} maxLength={100} className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2.5" />
            <button className="rounded-lg border border-slate-300 bg-white px-5 text-sm">검색</button>
        </form>
        {board.isAdmin && <div className="mb-4 flex flex-wrap items-center justify-between gap-3 text-sm text-blue-900"><label className="flex items-center gap-2"><input type="checkbox" checked={board.manage} onChange={event => board.setManage(event.target.checked)} />관리자: 임시저장·게시 취소 글도 보기</label><button onClick={() => void board.logout()} className="underline">관리자 로그아웃</button></div>}
        {board.error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-4 text-red-800">{board.error} <Link href="/login" className="underline">로그인 화면</Link></p>}
        <div aria-busy={board.loading} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            {board.loading ? <p role="status" className="p-10 text-center text-slate-500">게시글을 불러오는 중입니다.</p> : !board.posts.length ? <p className="p-12 text-center text-slate-500">{board.error ? '게시글을 불러오지 못했습니다.' : '등록된 게시글이 없습니다.'}</p> :
                <ul className="divide-y divide-slate-100">{board.posts.map(post => <li key={post.id}>
                    <Link href={`/board/${post.id}`} className="block px-5 py-5 transition hover:bg-blue-50/60 sm:px-6">
                        <div className="mb-2 flex gap-2 text-xs font-medium text-blue-800">
                            {post.is_pinned && <span className="rounded bg-blue-100 px-2 py-0.5">고정</span>}<span className="py-0.5">{BOARD_CATEGORIES[post.category]}</span>
                            {post.status === 'draft' && <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-800">비공개</span>}
                        </div>
                        <h2 className="break-words font-semibold">{post.title}</h2>
                        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500"><span>{post.author_name}</span><time>{boardDate(post.published_at || post.created_at)}</time>{post.attachments.length > 0 && <span>첨부 {post.attachments.length}</span>}</div>
                    </Link>
                </li>)}</ul>}
        </div>
        <nav aria-label="게시글 페이지" className="mt-6 flex items-center justify-center gap-5 text-sm">
            <button disabled={board.loading || board.page <= 1} onClick={() => board.setPage(board.page - 1)} className="rounded border px-4 py-2 disabled:opacity-40">이전</button>
            <span>{board.page} / {pages}</span>
            <button disabled={board.loading || board.page >= pages} onClick={() => board.setPage(board.page + 1)} className="rounded border px-4 py-2 disabled:opacity-40">다음</button>
        </nav>
        {!board.isAdmin && <BoardAdminLogin onLogin={board.reload} />}
    </>
}
