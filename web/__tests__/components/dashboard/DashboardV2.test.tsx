import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('@/utils/newArticleTracker', () => ({
    getLastVisitTime: vi.fn(() => null),
    updateLastVisitTime: vi.fn(),
    isArticleNew: vi.fn(() => false),
    countNewArticles: vi.fn(() => 0),
}))

vi.mock('@/components/ReportModal', () => ({
    default: () => null,
}))

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({ articles: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    vi.useRealTimers()
})

describe('DashboardV2', () => {
    it('keeps the mobile drawer closed on explicit category navigation from the board', async () => {
        vi.useFakeTimers()
        vi.stubGlobal('innerWidth', 375)
        const DashboardV2 = (await import('@/components/dashboard/DashboardV2')).default
        render(<DashboardV2 initialCategory="regulation_notice" isCategoryNavigation />)
        await act(async () => { await vi.advanceTimersByTimeAsync(150) })
        expect(screen.getByRole('button', { name: '전체 메뉴' })).toHaveAttribute('aria-expanded', 'false')
    })
    it('opens the requested regulation category and agency, while preserving sidebar switching', async () => {
        const DashboardV2 = (await import('@/components/dashboard/DashboardV2')).default
        fetchMock.mockResolvedValue({ ok: true, json: async () => ({ articles: [
            { id: 'reg', title: '규제개정 테스트 기사', category: 'regulation_notice', agency: 'FSC_REG', published_at: '2026-10-05T00:00:00Z', link: 'https://example.test/reg' },
            { id: 'press', title: '보도자료 테스트 기사', category: 'press_release', agency: 'FSC', published_at: '2026-10-05T00:00:00Z', link: 'https://example.test/press' },
        ] }) })
        render(<DashboardV2 initialCategory="regulation_notice" initialAgency="FSC_REG" />)
        fireEvent.click(screen.getByRole('button', { name: '리스트' }))
        expect(await screen.findByText('규제개정 테스트 기사')).toBeInTheDocument()
        expect(screen.queryByText('보도자료 테스트 기사')).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: '보도자료' }))
        expect(await screen.findByText('보도자료 테스트 기사')).toBeInTheDocument()
        expect(screen.queryByText('규제개정 테스트 기사')).not.toBeInTheDocument()
        expect(screen.getByRole('link', { name: '게시판' })).toHaveAttribute('href', '/board')
    })
    it('renders empty state when no articles', async () => {
        const DashboardV2 = (await import('@/components/dashboard/DashboardV2')).default
        render(<DashboardV2 />)
        await waitFor(() => {
            expect(screen.getByText('검색 결과가 없습니다.')).toBeInTheDocument()
        })
        expect(fetchMock).toHaveBeenCalledWith('/api/articles')
    })
})

describe('press agency navigation', () => {
    it('pressAgencies excludes MAFRA from the dashboard menu', async () => {
        const { pressAgencies } = await import('@/components/dashboard/constants')
        expect(pressAgencies).not.toContain('MAFRA')
    })
})
