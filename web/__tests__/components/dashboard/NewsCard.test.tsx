import { describe, it, expect, vi, afterEach } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import NewsCard, { type Article } from '@/components/dashboard/NewsCard'

afterEach(cleanup)

const baseArticle: Article = {
    id: 'article-1',
    title: '금융 규제 보도자료 제목',
    agency: 'FSC',
    category: 'press_release',
    published_at: '2026-05-04T00:05:00.000Z',
    created_at: '2026-05-04T03:15:00.000Z',
    link: 'https://example.com/article',
    analysis_result: {
        summary: ['요약'],
        importance_score: 4,
    },
}

function renderCard(article: Partial<Article> = {}) {
    const onGenerateReport = vi.fn()
    render(<NewsCard article={{ ...baseArticle, ...article }} onGenerateReport={onGenerateReport} />)
    return { onGenerateReport }
}

describe('NewsCard time display', () => {
    it('shows KST HH:mm for source rows', () => {
        renderCard({ published_at_source: 'source' })

        expect(screen.getByText('09:05')).toBeInTheDocument()
        expect(screen.queryByText('수집')).not.toBeInTheDocument()
    })

    it('shows created_at KST HH:mm for collected fallback rows without a source label', () => {
        renderCard({ published_at_source: 'collected_fallback' })

        expect(screen.getByText('12:15')).toBeInTheDocument()
        expect(screen.queryByText('09:05')).not.toBeInTheDocument()
        expect(screen.queryByText('수집')).not.toBeInTheDocument()
    })

    it('uses published_at KST HH:mm for null or missing published_at_source rows with a source time', () => {
        renderCard({ id: 'null-source', published_at_source: null })
        expect(screen.getByText('09:05')).toBeInTheDocument()
        cleanup()

        renderCard({ id: 'missing-source' })
        expect(screen.getByText('09:05')).toBeInTheDocument()
    })

    it('uses created_at for legacy rows whose published_at is KST midnight', () => {
        renderCard({
            published_at: '2026-05-03T15:00:00.000Z',
            created_at: '2026-05-04T03:15:00.000Z',
            published_at_source: null,
        })

        expect(screen.getByText('12:15')).toBeInTheDocument()
        expect(screen.queryByText('00:00')).not.toBeInTheDocument()
        expect(screen.queryByText('수집')).not.toBeInTheDocument()
    })

    it('keeps NEW badge tied to article.isNew', () => {
        renderCard({ isNew: true })

        expect(screen.getByText('NEW')).toBeInTheDocument()
    })

    it('does not render invalid time text, placeholder, or source label for invalid dates', () => {
        renderCard({
            title: '날짜가 없어도 렌더링되는 기사',
            published_at: '',
            created_at: 'not-a-date',
            published_at_source: 'collected_fallback',
        })

        expect(screen.getByText('날짜가 없어도 렌더링되는 기사')).toBeInTheDocument()
        expect(screen.getByText('금융위')).toBeInTheDocument()
        expect(screen.queryByText('Invalid Date')).not.toBeInTheDocument()
        expect(screen.queryByText('NaN')).not.toBeInTheDocument()
        expect(screen.queryByText('수집')).not.toBeInTheDocument()
        expect(screen.queryByTestId('news-card-time')).not.toBeInTheDocument()
    })
})

describe('NewsCard mobile layout', () => {
    it('keeps long fallback rows constrained and ordered on the right column', () => {
        renderCard({
            title: '한국어로 매우 길게 작성된 금융감독원 제도개선 보도자료 제목이 모바일 카드에서 두 줄 이상으로 이어져도 배지와 오른쪽 시각 컬럼을 침범하지 않아야 합니다',
            agency: 'FSC_REG',
            category: 'regulation_notice',
            published_at_source: 'collected_fallback',
            isNew: true,
        })

        const left = screen.getByTestId('news-card-left')
        const right = screen.getByTestId('news-card-right')

        expect(left.className).toContain('min-w-0')
        expect(right.className).toContain('shrink-0')
        expect(right.className).toContain('min-w-[64px]')
        expect(within(left).getByText('NEW')).toBeInTheDocument()

        const children = Array.from(right.children)
        expect(children[0]).toHaveTextContent('12:15')
        expect(children[1].querySelectorAll('svg')).toHaveLength(5)
        expect(children[2].tagName.toLowerCase()).toBe('svg')
    })
})
