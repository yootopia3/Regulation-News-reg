import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
const mocks = vi.hoisted(() => ({ boardRequest: vi.fn() }))
vi.mock('@/lib/board/client', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/board/client')>(), boardRequest: mocks.boardRequest }))
import BoardComments from '@/components/board/BoardComments'
import BoardDetail from '@/components/board/BoardDetail'
const postId = '00000000-0000-4000-8000-000000000001'
const comment = { id: '00000000-0000-4000-8000-000000000002', post_id: postId, author_name: '담당자', body: '검토 의견', revision: 7, created_at: '2026-10-09T00:00:00Z', updated_at: '2026-10-09T00:00:00Z' }
let comments: typeof comment[]
let admin: boolean
beforeEach(() => {
    vi.clearAllMocks(); comments = []; admin = false
    mocks.boardRequest.mockImplementation(async (url, init) => {
        if (init?.method === 'POST') { const input = JSON.parse(init.body); comments = [{ ...comment, author_name: input.author_name, body: input.body, revision: 0 }, ...comments]; return { comment: comments[0] } }
        if (init?.method === 'DELETE') { comments = []; return { ok: true } }
        if (init?.method === 'PATCH') { const input = JSON.parse(init.body); comments = [{ ...comments[0], body: input.body, revision: comments[0].revision + 1 }]; return { comment: comments[0] } }
        return { comments, total: comments.length, page: 1, isAdmin: admin }
    })
})
afterEach(cleanup)
describe('board comment workflows', () => {
    it('creates a comment below the list and clears content/password on success', async () => {
        render(<BoardComments postId={postId} />)
        expect(await screen.findByText('첫 댓글을 남겨보세요.')).toBeInTheDocument()
        await userEvent.type(screen.getByLabelText('댓글 작성자 이름'), '새 작성자')
        await userEvent.type(screen.getByLabelText('댓글 내용'), '새 의견')
        await userEvent.type(screen.getByLabelText('댓글 비밀번호'), 'test-comment-password')
        await userEvent.click(screen.getByRole('button', { name: '댓글 등록' }))
        expect(await screen.findByText('새 의견')).toBeInTheDocument()
        expect(screen.getByText('댓글이 등록되었습니다.')).toBeInTheDocument()
        expect(screen.getByLabelText('댓글 내용')).toHaveValue('')
        expect(screen.getByLabelText('댓글 비밀번호')).toHaveValue('')
        const call = mocks.boardRequest.mock.calls.find(([, init]) => init?.method === 'POST')!
        expect(JSON.parse(call[1].body)).toEqual({ author_name: '새 작성자', body: '새 의견', password: 'test-comment-password' })
        expect(mocks.boardRequest.mock.lastCall?.[0]).toBe(`/api/board/${postId}/comments?page=1`)
    })
    it('requires a separate confirmation and comment password before deletion', async () => {
        comments = [comment]; render(<BoardComments postId={postId} />)
        await userEvent.click(await screen.findByRole('button', { name: '담당자 댓글 삭제' }))
        expect(mocks.boardRequest.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
        await userEvent.type(screen.getByLabelText('댓글 확인 비밀번호'), 'test-comment-password')
        await userEvent.click(screen.getByRole('button', { name: '댓글 삭제 확인' }))
        expect(await screen.findByText('댓글이 삭제되었습니다.')).toBeInTheDocument()
        expect(screen.queryByText('검토 의견')).not.toBeInTheDocument()
        const call = mocks.boardRequest.mock.calls.find(([, init]) => init?.method === 'DELETE')!
        expect(JSON.parse(call[1].body)).toEqual({ revision: 7, password: 'test-comment-password' })
    })
    it('keeps an edit on a password error and sends the original revision on retry', async () => {
        comments = [comment]
        const normal = mocks.boardRequest.getMockImplementation()!
        let allow = false
        mocks.boardRequest.mockImplementation(async (url, init) => {
            if (init?.method === 'PATCH' && !allow) throw new Error('댓글 비밀번호가 올바르지 않습니다.')
            return normal(url, init)
        })
        render(<BoardComments postId={postId} />)
        await userEvent.click(await screen.findByRole('button', { name: '담당자 댓글 수정' }))
        fireEvent.change(screen.getByLabelText('수정할 댓글'), { target: { value: '수정 의견' } })
        await userEvent.type(screen.getByLabelText('댓글 확인 비밀번호'), 'wrong-password')
        await userEvent.click(screen.getByRole('button', { name: '수정 저장' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('올바르지 않습니다')
        expect(screen.getByLabelText('수정할 댓글')).toHaveValue('수정 의견')
        allow = true
        fireEvent.change(screen.getByLabelText('댓글 확인 비밀번호'), { target: { value: 'test-comment-password' } })
        await userEvent.click(screen.getByRole('button', { name: '수정 저장' }))
        expect(await screen.findByText('댓글이 수정되었습니다.')).toBeInTheDocument()
        expect(screen.getByText('수정 의견')).toBeInTheDocument()
        expect(screen.queryByLabelText('댓글 확인 비밀번호')).not.toBeInTheDocument()
        const calls = mocks.boardRequest.mock.calls.filter(([, init]) => init?.method === 'PATCH')
        expect(JSON.parse(calls[1][1].body)).toEqual({ revision: 7, password: 'test-comment-password', body: '수정 의견' })
    })
    it('lets verified administrators moderate without a comment password and renders user text literally', async () => {
        admin = true; comments = [{ ...comment, body: '<script>alert(1)</script>\n![image](https://example.test/pixel)' }]
        const { container } = render(<BoardComments postId={postId} />)
        expect(await screen.findByText(/<script>alert/)).toBeInTheDocument()
        expect(container.querySelector('script')).toBeNull(); expect(container.querySelector('img')).toBeNull()
        await userEvent.click(screen.getByRole('button', { name: '담당자 댓글 삭제' }))
        expect(screen.queryByLabelText('댓글 확인 비밀번호')).not.toBeInTheDocument()
        await userEvent.click(screen.getByRole('button', { name: '댓글 삭제 확인' }))
        expect(await screen.findByText('댓글이 삭제되었습니다.')).toBeInTheDocument()
    })
    it('provides retry on loading errors and does not permit writing before a successful load', async () => {
        mocks.boardRequest.mockRejectedValueOnce(new Error('댓글 연결을 확인해주세요.'))
        render(<BoardComments postId={postId} />)
        expect(await screen.findByRole('alert')).toHaveTextContent('연결')
        expect(screen.getByRole('button', { name: '댓글 등록' })).toBeDisabled()
        await userEvent.click(screen.getByRole('button', { name: '댓글 다시 불러오기' }))
        expect(await screen.findByText('첫 댓글을 남겨보세요.')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: '댓글 등록' })).toBeEnabled()
    })
    it('paginates and recovers when concurrent deletion empties the last page', async () => {
        mocks.boardRequest.mockImplementation(async url => url.endsWith('page=2')
            ? { comments: [], total: 20, page: 2, isAdmin: false }
            : { comments: [comment], total: 21, page: 1, isAdmin: false })
        render(<BoardComments postId={postId} />)
        await userEvent.click(await screen.findByRole('button', { name: '다음 댓글' }))
        await waitFor(() => expect(mocks.boardRequest.mock.calls.filter(([url]) => url.endsWith('page=1'))).toHaveLength(2))
        expect(await screen.findByText('검토 의견')).toBeInTheDocument()
        expect(screen.getByText('1 / 2')).toBeInTheDocument()
    })
    it('shows the comment section only after loading a published parent', async () => {
        const post = { id: postId, title: '업무 글', author_name: '작성자', body: '본문', category: 'general', status: 'draft', is_pinned: false, attachments: [], created_at: comment.created_at, published_at: null }
        mocks.boardRequest.mockResolvedValue({ post, isAdmin: true })
        const { unmount } = render(<BoardDetail id={postId} />)
        expect(await screen.findByText('업무 글')).toBeInTheDocument()
        expect(screen.queryByRole('region', { name: '댓글' })).not.toBeInTheDocument()
        expect(mocks.boardRequest.mock.calls.some(([url]) => url.includes('/comments'))).toBe(false)
        unmount()
        mocks.boardRequest.mockImplementation(async url => url.includes('/comments') ? { comments: [], total: 0, isAdmin: false } : { post: { ...post, status: 'published' }, isAdmin: false })
        render(<BoardDetail id={postId} />)
        expect(await screen.findByText('첫 댓글을 남겨보세요.')).toBeInTheDocument()
    })
})
