import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import SanctionReportsPage from '@/app/reports/sanctions/page'
import Sidebar, { type SidebarProps } from '@/components/dashboard/Sidebar'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const rows = [
    { id: 'one', title: '토스뱅크 제재', agency: 'FSS_SANCTION', category: 'sanction_notice', published_at: '2026-09-10', link: 'https://www.fss.or.kr/fss/one', analysis_result: { summary: ['공개 요약'] } },
    { id: 'two', title: '예시은행 경영유의', agency: 'FSS_MGMT_NOTICE', category: 'sanction_notice', published_at: '2026-09-09', link: 'https://www.fss.or.kr/fss/two' },
]

describe('sanction reports page', () => {
    it('loads actual sources, searches, filters, and identifies analysis as not yet connected', async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ articles: rows })))
        vi.stubGlobal('fetch', fetchMock)
        render(<SanctionReportsPage />)
        expect(screen.getByText('공시를 불러오는 중입니다…')).toBeInTheDocument()
        await screen.findByText('토스뱅크 제재')
        expect(screen.getByText('제재사례를 사고예방 점검으로 연결하세요')).toBeInTheDocument()
        fireEvent.change(screen.getByRole('searchbox'), { target: { value: '토스' } })
        expect(screen.queryByText('예시은행 경영유의')).not.toBeInTheDocument()
        fireEvent.change(screen.getByRole('combobox'), { target: { value: 'FSS_MGMT_NOTICE' } })
        expect(screen.getByText('검색 조건에 맞는 공시가 없습니다.')).toBeInTheDocument()
        expect(fetchMock.mock.calls.every(call => call[0] === '/api/articles')).toBe(true)
    })
    it('distinguishes session expiry from empty results', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
        render(<SanctionReportsPage />)
        expect(await screen.findByRole('link', { name: '다시 로그인' })).toHaveAttribute('href', '/login')
        expect(screen.queryByText('수집된 제재공시가 없습니다.')).not.toBeInTheDocument()
    })
    it('offers retry after failure and shows a true empty response', async () => {
        vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(new Response(JSON.stringify({ articles: [] }))))
        render(<SanctionReportsPage />)
        fireEvent.click(await screen.findByRole('button', { name: '다시 시도' }))
        await screen.findByText('수집된 제재공시가 없습니다.')
    })
    it('keeps the existing report and adds the requested submenu inside Report', async () => {
        const noop = () => {}
        const props: SidebarProps = { isMenuOpen: true, onCloseMenu: noop, currentCategory: 'press_release', selectedAgency: null, onSelectHome: noop, onSelectPress: noop, onSelectReg: noop, onSelectSanction: noop, isAgencyExpanded: false, isRegExpanded: false, isFSSRegGroupExpanded: false, isSanctionExpanded: false, onToggleAgency: noop, onToggleReg: noop, onToggleFSSRegGroup: noop, onToggleSanction: noop, hasNewPress: false, hasNewReg: false, hasNewSanction: false }
        render(<Sidebar {...props} />)
        expect(screen.queryByRole('link', { name: '재제공시 리포트' })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Report' }))
        await waitFor(() => expect(screen.getByRole('link', { name: '재제공시 리포트' })).toHaveAttribute('href', '/reports/sanctions'))
        expect(screen.getByRole('link', { name: '아침에 읽는 규제변화' })).toHaveAttribute('href', '/api/daily-report')
    })
})
