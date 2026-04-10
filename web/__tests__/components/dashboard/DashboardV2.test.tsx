import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('@/utils/supabase/client', () => {
    const chain: any = {}
    chain.from = vi.fn(() => chain)
    chain.select = vi.fn(() => chain)
    chain.in = vi.fn(() => chain)
    chain.eq = vi.fn(() => chain)
    chain.or = vi.fn(() => chain)
    chain.order = vi.fn(() => chain)
    chain.limit = vi.fn(() => Promise.resolve({ data: [], error: null }))
    return { supabase: chain }
})

vi.mock('@/utils/newArticleTracker', () => ({
    getLastVisitTime: vi.fn(() => null),
    updateLastVisitTime: vi.fn(),
    isArticleNew: vi.fn(() => false),
    countNewArticles: vi.fn(() => 0),
}))

vi.mock('@/components/ReportModal', () => ({
    default: () => null,
}))

describe('DashboardV2', () => {
    it('renders empty state when no articles', async () => {
        const DashboardV2 = (await import('@/components/dashboard/DashboardV2')).default
        render(<DashboardV2 />)
        await waitFor(() => {
            expect(screen.getByText('검색 결과가 없습니다.')).toBeInTheDocument()
        })
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
