import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'

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
})

describe('DashboardV2', () => {
    it('renders empty state when no articles', async () => {
        const DashboardV2 = (await import('@/components/dashboard/DashboardV2')).default
        render(<DashboardV2 />)
        await waitFor(() => {
            expect(screen.getByText('검색 결과가 없습니다.')).toBeInTheDocument()
        })
        expect(fetchMock).toHaveBeenCalledWith('/api/articles')
    })
})

describe('MAFRA integration', () => {
    it('pressAgencies includes MAFRA', async () => {
        const { pressAgencies } = await import('@/components/dashboard/constants')
        expect(pressAgencies).toContain('MAFRA')
    })

    it('agencyNames maps MAFRA to 농식품부', async () => {
        const { agencyNames } = await import('@/components/dashboard/constants')
        expect(agencyNames['MAFRA']).toBe('농식품부')
    })
})
