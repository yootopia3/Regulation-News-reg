import { afterEach, describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import Page from '@/app/admin/inspections/page'
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
describe('inspection administrator screen', () => {
    it('selects an article, submits only its ID and displays pending status', async () => {
        const data = { enabled: true, articles: [{ id: 'article', title: '합성 공시' }], jobs: [] }
        const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(data)))
            .mockResolvedValueOnce(new Response('{"id":"job"}'))
            .mockResolvedValueOnce(new Response(JSON.stringify({ ...data, jobs: [{ id: 'job', article_id: 'article', status: 'queued' }] })))
        vi.stubGlobal('fetch', fetchMock)
        render(<Page />)
        await screen.findByRole('option', { name: '합성 공시' })
        fireEvent.change(screen.getByRole('combobox'), { target: { value: 'article' } })
        fireEvent.click(screen.getByRole('button', { name: '분석 실행' }))
        await screen.findByText('분석 대기')
        expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ article_id: 'article', request_id: expect.any(String) })
    })
    it('renders department proposals, checks and private references without a publish button', async () => {
        const job = { id: 'job', article_id: 'article', status: 'needs_review', result: { findings: [{ id: 'F1', title: '합성 지적', summary: '요약', evidence: [{ page: 2, quote: '공개 근거' }] }], matches: [{ finding_id: 'F1', department: '합성부', rationale: '검토 이유', checks: [{ question: '확인했는가?', evidence_to_request: '승인 이력' }], evidence: [{ ref: 'doc:1', quote: '합성 내부 근거' }] }], unmatched_finding_ids: [] } }
        vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ enabled: true, articles: [], jobs: [job] }))).mockResolvedValueOnce(new Response(JSON.stringify({ job }))))
        render(<Page />)
        fireEvent.click(await screen.findByRole('button', { name: '초안 확인' }))
        await screen.findByText('후보 부서: 합성부')
        expect(screen.getByText('확인했는가?', { selector: 'li' })).toBeInTheDocument()
        expect(screen.getByText('doc:1: 합성 내부 근거')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: '검토본 게시' })).toBeDisabled()
    })
})
