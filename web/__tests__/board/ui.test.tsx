import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
const mocks = vi.hoisted(() => ({ boardRequest: vi.fn(), push: vi.fn() }))
vi.mock('@/lib/board/client', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/board/client')>(), boardRequest: mocks.boardRequest }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: mocks.push }) }))
import BoardBody from '@/components/board/BoardBody'
import BoardList from '@/components/board/BoardList'
import BoardEditor from '@/components/board/BoardEditor'
const post = { id: '00000000-0000-4000-8000-000000000001', title: '자료 안내', author_name: '담당자', body: '본문 내용', category: 'general', status: 'published', is_pinned: false, revision: 0, created_at: '2026-10-05T00:00:00Z', updated_at: '2026-10-05T00:00:00Z', published_at: '2026-10-05T00:00:00Z', attachments: [] }
afterEach(cleanup)
beforeEach(() => { vi.clearAllMocks() })
describe('board user workflows', () => {
    it('displays safe formatting without script, raw HTML, external image or javascript execution', () => {
        const { container } = render(<BoardBody body={'**중요**\n\n<script>alert(1)</script>\n\n[위험](javascript:alert)\n\n![external](https://example.test/pixel.png)'} />)
        expect(screen.getByText('중요').tagName).toBe('STRONG')
        expect(container.querySelector('script')).toBeNull()
        expect(container.querySelector('img')).toBeNull()
        expect(container.querySelector('a')?.getAttribute('href')).not.toMatch(/^javascript:/)
    })
    it('searches and changes category with the first page, and offers a write link', async () => {
        mocks.boardRequest.mockResolvedValue({ posts: [post], total: 21, isAdmin: false })
        render(<BoardList />)
        expect(await screen.findByText('자료 안내')).toBeInTheDocument()
        expect(screen.getByRole('link', { name: '글쓰기' })).toHaveAttribute('href', '/board/new')
        await userEvent.click(screen.getByRole('button', { name: '다음' }))
        await waitFor(() => expect(mocks.boardRequest.mock.lastCall?.[0]).toContain('page=2'))
        await userEvent.type(screen.getByRole('textbox', { name: '제목·본문 검색' }), '개정')
        await userEvent.click(screen.getByRole('button', { name: '검색' }))
        await waitFor(() => expect(mocks.boardRequest.mock.lastCall?.[0]).toContain('page=1'))
        expect(mocks.boardRequest.mock.lastCall?.[0]).toContain(encodeURIComponent('개정'))
        await userEvent.click(screen.getByRole('button', { name: '자료실' }))
        await waitFor(() => expect(mocks.boardRequest.mock.lastCall?.[0]).toContain('category=resources'))
    })
    it('saves a private draft with its password and offers a durable management link', async () => {
        mocks.boardRequest.mockImplementation(async (_url, init) => init?.method === 'POST' ? { post: { ...post, status: 'draft' } } : { posts: [], total: 0, isAdmin: false })
        render(<BoardEditor />)
        await waitFor(() => expect(screen.getByLabelText('작성자 이름')).toBeEnabled())
        await userEvent.type(screen.getByLabelText('작성자 이름'), '담당자')
        await userEvent.type(screen.getByLabelText('제목'), '자료 안내')
        await userEvent.type(screen.getByRole('textbox', { name: '본문' }), '본문 내용')
        await userEvent.type(screen.getByLabelText(/글 비밀번호/), 'new-test-password')
        await userEvent.click(screen.getByRole('button', { name: '임시저장' }))
        expect(await screen.findByText('글이 임시저장되었습니다.')).toBeInTheDocument()
        const call = mocks.boardRequest.mock.calls.find(([, init]) => init?.method === 'POST')!
        expect(JSON.parse(call[1].body.get('payload'))).toMatchObject({ status: 'draft', password: 'new-test-password' })
        expect(screen.getByRole('link', { name: /글 관리 링크/ })).toHaveAttribute('href', `/board/${post.id}/edit`)
        expect(screen.queryByDisplayValue('new-test-password')).not.toBeInTheDocument()
    })
    it('does not reveal the editor after an incorrect password, then preserves revision for an authorized update', async () => {
        let allow = false
        mocks.boardRequest.mockImplementation(async (url, init) => {
            if (url.endsWith('/unlock')) { if (!allow) throw new Error('글 비밀번호가 올바르지 않습니다.'); return { post: { ...post, revision: 7 }, isAdmin: false } }
            if (init?.method === 'PATCH') return { post: { ...post, revision: 8, status: 'draft' } }
            return { isAdmin: false, posts: [], total: 0 }
        })
        render(<BoardEditor id={post.id} />)
        await userEvent.type(screen.getByLabelText('글 비밀번호'), 'test-post-password')
        await userEvent.click(screen.getByRole('button', { name: '확인' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('올바르지 않습니다')
        expect(screen.queryByLabelText('제목')).not.toBeInTheDocument()
        allow = true
        await userEvent.click(screen.getByRole('button', { name: '확인' }))
        expect(await screen.findByLabelText('제목')).toHaveValue('자료 안내')
        await userEvent.click(screen.getByRole('button', { name: '게시 취소·임시저장' }))
        expect(await screen.findByText('글이 임시저장되었습니다.')).toBeInTheDocument()
        const call = mocks.boardRequest.mock.calls.find(([, init]) => init?.method === 'PATCH')!
        expect(JSON.parse(call[1].body.get('payload'))).toMatchObject({ revision: 7, password: 'test-post-password', status: 'draft' })
    })
    it('requires an explicit second action to delete a post', async () => {
        mocks.boardRequest.mockImplementation(async url => url.endsWith('/unlock') ? { post, isAdmin: true } : { isAdmin: true, posts: [], total: 0 })
        render(<BoardEditor id={post.id} />)
        await userEvent.click(await screen.findByRole('button', { name: '관리자 권한으로 열기' }))
        await userEvent.click(await screen.findByRole('button', { name: '글 삭제' }))
        expect(mocks.boardRequest.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
        await userEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
        await waitFor(() => expect(mocks.push).toHaveBeenCalledWith('/board'))
    })
    it('offers administrator logout and clears private management mode', async () => {
        let admin = true
        mocks.boardRequest.mockImplementation(async url => {
            if (url === '/api/admin/logout') { admin = false; return { ok: true } }
            return { isAdmin: admin, posts: [], total: 0 }
        })
        render(<BoardList />)
        fireEvent.click(await screen.findByRole('checkbox'))
        await userEvent.click(screen.getByRole('button', { name: '관리자 로그아웃' }))
        await waitFor(() => expect(screen.queryByRole('checkbox')).not.toBeInTheDocument())
        expect(mocks.boardRequest.mock.calls.some(([url, init]) => url === '/api/admin/logout' && init.method === 'POST')).toBe(true)
        expect(mocks.boardRequest.mock.lastCall?.[0]).toContain('manage=0')
    })
})
