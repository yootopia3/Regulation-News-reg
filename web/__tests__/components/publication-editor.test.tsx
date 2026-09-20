import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import PublicationEditor from '@/components/PublicationEditor'
import PublishedInspections from '@/components/PublishedInspections'
import { initialReport, publicReport, validatePublication } from '@/lib/publication'
import type { InspectionDraft } from '@/lib/inspection-ui'

const report = { items: [{ finding_id: 'F1', title: '합성 공개 지적', summary: '요약', departments: ['확인부'], related_work: '확인 업무', source_pages: [1], checks: [{ question: '승인 기록을 확인했는가?', evidence_to_request: '승인 기록' }] }] }
const job = { id: 'job', article_id: 'article', status: 'needs_review', error_code: null, review_revision: 3, review_draft: report }
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
describe('publication review UI', () => {
    it('saves an added master check with an owner and synchronizes removed departments', async () => {
        const draft: InspectionDraft = { analysis_basis: 'duty_master', master_version: 'fixture-v1', master_fingerprint: 'a'.repeat(64),
            findings: [{ id: 'F1', title: '공개 지적', summary: '공개 요약', evidence: [{ page: 1, quote: '공개 근거' }] }],
            matches: ['확인부', '지원부'].map((department, i) => ({ finding_id: 'F1', department, rationale: '후보',
                related_work: '후속 조치 확인', duty_ids: [`HQ-00${i+1}`], duty_basis: 'inferred', evidence: [],
                checks: [{ question: '완료 처리된 건에 확인 증빙이 있는가?', evidence_to_request: '이력' }] })), unmatched_finding_ids: [] }
        const fetchMock = vi.fn().mockResolvedValue(new Response('{"revision":4}'))
        vi.stubGlobal('fetch', fetchMock)
        render(<PublicationEditor job={{ ...job, result: draft, review_draft: initialReport(draft) }} />)
        fireEvent.click(screen.getByRole('button', { name: '점검 항목 추가' }))
        expect(screen.getByLabelText('담당 후보 3')).toHaveValue('확인부')
        fireEvent.change(screen.getByLabelText('점검 질문 3'), { target: { value: '미완료 건은 추적하고 있는가?' } })
        fireEvent.change(screen.getByLabelText('요청 증빙 3'), { target: { value: '미완료 목록' } })
        fireEvent.click(screen.getByRole('checkbox', { name: '지원부 · 업무 귀속 추정' }))
        expect(screen.queryByLabelText('담당 후보 3')).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: '검토본 저장' }))
        await screen.findByText('검토본을 저장했습니다. 기존 게시본이 있다면 철회됩니다.')
        const saved = publicReport(JSON.parse(fetchMock.mock.calls[0][1].body).report)
        expect(saved.items[0].departments).toEqual(['확인부'])
        expect(saved.items[0].department_basis).toHaveLength(1)
        expect(saved.items[0].checks).toHaveLength(2)
        expect(() => validatePublication(saved, draft, [])).not.toThrow()
    })
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
