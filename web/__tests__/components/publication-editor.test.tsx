import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import PublicationEditor from '@/components/PublicationEditor'
import PublishedInspections from '@/components/PublishedInspections'

const report = { items: [{ finding_id: 'F1', title: '합성 공개 지적', summary: '요약', departments: ['확인부'], related_work: '확인 업무', source_pages: [1], checks: [{ question: '승인 기록을 확인했는가?', evidence_to_request: '승인 기록' }] }] }
const job = { id: 'job', article_id: 'article', status: 'needs_review', error_code: null, review_revision: 3, review_draft: report }
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
describe('publication review UI', () => {
    it('requires saved edits and explicit review, keeping unsaved changes blocked after withdrawal', async () => {
        const fetchMock = vi.fn().mockResolvedValueOnce(new Response('{"revision":4}')).mockResolvedValueOnce(new Response('{"revision":5}'))
        vi.stubGlobal('fetch', fetchMock)
        render(<PublicationEditor job={job} />)
        expect(screen.getByRole('button', { name: '검토본 게시' })).toBeDisabled()
        fireEvent.click(screen.getByRole('checkbox'))
        expect(screen.getByRole('button', { name: '검토본 게시' })).toBeEnabled()
        fireEvent.change(screen.getByLabelText('관련 업무'), { target: { value: '수정된 확인 업무' } })
        expect(screen.getByRole('checkbox')).toBeDisabled()
        fireEvent.click(screen.getByRole('button', { name: '게시 철회' }))
        await screen.findByText('게시를 철회했습니다.')
        expect(screen.getByRole('checkbox')).toBeDisabled()
        fireEvent.click(screen.getByRole('button', { name: '검토본 저장' }))
        await screen.findByText('검토본을 저장했습니다. 기존 게시본이 있다면 철회됩니다.')
        expect(screen.getByRole('checkbox')).toBeEnabled()
        expect(JSON.parse(fetchMock.mock.calls[1][1].body).revision).toBe(4)
    })
    it('shows only published report fields and provides the authenticated Excel link', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ reports: [{ id: 'report', article_id: 'article', published_at: '2026-09-10', report, source: { title: '합성 은행 공시', url: 'https://www.fss.or.kr/fss/notice', published_at: '2026-09-09' } }], enabled: true, nextOffset: null }))))
        render(<PublishedInspections />)
        fireEvent.click(screen.getByRole('button', { name: '리포트 조회' }))
        await screen.findByText('합성 공개 지적')
        expect(screen.getByText('합성 은행 공시')).toBeInTheDocument()
        expect(screen.getByRole('link', { name: '금감원 공시 원문 열기' })).toHaveAttribute('href', 'https://www.fss.or.kr/fss/notice')
        expect(screen.getByText('승인 기록을 확인했는가?')).toBeInTheDocument()
        expect(screen.getByRole('link', { name: '점검표 Excel 다운로드' })).toHaveAttribute('href', '/api/sanction-publications?id=report&format=xlsx')
        expect(screen.queryByText('내부 근거')).not.toBeInTheDocument()
    })
})
