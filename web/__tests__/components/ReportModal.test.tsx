import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import ReportModal from '@/components/ReportModal'
import type { Article } from '@/components/dashboard/NewsCard'

afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
})

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

function jsonResponse(body: Record<string, unknown>, status = 200) {
    return new Response(JSON.stringify(body), {
        status,
        headers: { 'content-type': 'application/json' },
    })
}

function renderModal(article: Article | null = baseArticle, isOpen = true) {
    return render(
        <ReportModal
            isOpen={isOpen}
            onClose={() => {}}
            article={article}
        />,
    )
}

describe('ReportModal', () => {
    it('calls /api/report once with articleId-only body and avoids duplicate fetch for the same article id', async () => {
        const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ report: '리포트 본문' }))
        vi.stubGlobal('fetch', fetchMock)

        const { rerender } = renderModal()

        await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
        expect(await screen.findByText('리포트 본문')).toBeInTheDocument()

        const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
        expect(url).toBe('/api/report')
        expect(init.method).toBe('POST')
        expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
        expect(JSON.parse(init.body as string)).toEqual({ articleId: 'article-1' })

        rerender(
            <ReportModal
                isOpen={true}
                onClose={() => {}}
                article={{ ...baseArticle, title: '변경된 제목' }}
            />,
        )
        await act(async () => {
            await Promise.resolve()
        })

        expect(fetchMock).toHaveBeenCalledTimes(1)
    })

    it('resets visible report content when closed and ignores a late response', async () => {
        let resolveFirstFetch: (value: Response) => void = () => {}
        const firstFetch = new Promise<Response>((resolve) => {
            resolveFirstFetch = resolve
        })
        const fetchMock = vi
            .fn()
            .mockReturnValueOnce(firstFetch)
            .mockResolvedValueOnce(jsonResponse({ report: '새 리포트' }))
        vi.stubGlobal('fetch', fetchMock)

        const { rerender } = renderModal()
        await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

        rerender(
            <ReportModal
                isOpen={false}
                onClose={() => {}}
                article={baseArticle}
            />,
        )
        expect(screen.queryByText('늦은 리포트')).not.toBeInTheDocument()

        await act(async () => {
            resolveFirstFetch(jsonResponse({ report: '늦은 리포트' }))
            await firstFetch
        })

        rerender(
            <ReportModal
                isOpen={true}
                onClose={() => {}}
                article={baseArticle}
            />,
        )

        expect(screen.queryByText('늦은 리포트')).not.toBeInTheDocument()
        await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
        expect(await screen.findByText('새 리포트')).toBeInTheDocument()
    })

    it('shows markdown error and stops loading when the API returns an error', async () => {
        const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
        const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ error: '서버 오류' }, 500))
        vi.stubGlobal('fetch', fetchMock)

        renderModal()

        expect(screen.getByText('리포트 생성 중...')).toBeInTheDocument()
        expect(await screen.findByText('서버 오류')).toBeInTheDocument()
        expect(screen.queryByText('리포트 생성 중...')).not.toBeInTheDocument()
        expect(consoleError).toHaveBeenCalled()
    })
})
