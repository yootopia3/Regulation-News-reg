import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
const navigation = vi.hoisted(() => ({ push: vi.fn(), pathname: '/board' }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: navigation.push }), usePathname: () => navigation.pathname }))
import BoardShell from '@/components/board/BoardShell'
import { dashboardHref, dashboardSelection } from '@/components/dashboard/navigation'
afterEach(cleanup)
beforeEach(() => { vi.clearAllMocks(); navigation.pathname = '/board' })

describe('shared board navigation', () => {
    it.each(['/board', '/board/new', '/board/post-id', '/board/post-id/edit'])('keeps the sidebar and active board entry at %s', path => {
        navigation.pathname = path
        render(<BoardShell><p>해당 페이지 내용</p></BoardShell>)
        const menu = screen.getByRole('navigation', { name: '주 메뉴' })
        expect(within(menu).getByRole('button', { name: '보도자료' })).toBeInTheDocument()
        expect(within(menu).getByRole('button', { name: '규제개정' })).toBeInTheDocument()
        expect(within(menu).getByRole('link', { name: '게시판' })).toHaveAttribute('aria-current', 'page')
        expect(within(menu).queryByText('스크랩 보관함')).not.toBeInTheDocument()
        expect(screen.getByText('v3.0.0 (Beta)')).toBeInTheDocument()
        expect(within(screen.getByRole('main')).getByText('해당 페이지 내용')).toBeInTheDocument()
        expect(screen.queryByRole('link', { name: /아침에 읽는 규제변화/ })).not.toBeInTheDocument()
    })
    it('opens and closes the shared mobile menu and closes it when selecting the board', () => {
        render(<BoardShell><p>목록</p></BoardShell>)
        const button = screen.getByRole('button', { name: '전체 메뉴' })
        expect(button).toHaveAttribute('aria-expanded', 'false')
        fireEvent.click(button)
        expect(button).toHaveAttribute('aria-expanded', 'true')
        const boardLink = within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name: '게시판' })
        // JSDOM does not implement browser navigation; still exercise the real close handler.
        boardLink.addEventListener('click', event => event.preventDefault(), { once: true })
        fireEvent.click(boardLink)
        expect(button).toHaveAttribute('aria-expanded', 'false')
        fireEvent.click(button); fireEvent.click(button)
        expect(button).toHaveAttribute('aria-expanded', 'false')
    })
    it.each([['보도자료','press_release'], ['규제개정','regulation_notice'], ['제재 공시','sanction_notice']])('returns to the selected %s category', (label, category) => {
        render(<BoardShell><p>목록</p></BoardShell>)
        fireEvent.click(screen.getByRole('button', { name: '전체 메뉴' }))
        fireEvent.click(screen.getByRole('button', { name: label }))
        expect(navigation.push).toHaveBeenCalledWith(`/?category=${category}`)
        expect(screen.getByRole('button', { name: '전체 메뉴' })).toHaveAttribute('aria-expanded', 'false')
    })
    it('shows a breadcrumb for editing and keeps home navigation', () => {
        navigation.pathname = '/board/id/edit'
        render(<BoardShell><p>편집 내용</p></BoardShell>)
        expect(within(screen.getByRole('navigation', { name: '현재 위치' })).getByText('글 수정·삭제')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: '홈으로 이동' }))
        expect(navigation.push).toHaveBeenCalledWith('/')
    })
})
describe('dashboard URL selection', () => {
    it('preserves allowed category/agency combinations and rejects invalid query values', () => {
        expect(dashboardSelection('regulation_notice','FSS_REG_INFO')).toEqual({ category: 'regulation_notice', agency: 'FSS_REG_INFO' })
        expect(dashboardHref('sanction_notice','FSS_SANCTION')).toBe('/?category=sanction_notice&agency=FSS_SANCTION')
        expect(dashboardSelection('regulation_notice','FSC')).toEqual({ category: 'regulation_notice', agency: null })
        expect(dashboardSelection(['press_release'],['FSS'])).toEqual({ category: 'press_release', agency: null })
        expect(dashboardSelection('__proto__','toString')).toEqual({ category: 'press_release', agency: null })
    })
})
