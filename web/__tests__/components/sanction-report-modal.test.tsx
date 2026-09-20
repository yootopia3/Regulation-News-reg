import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import ReportModal from '@/components/ReportModal'
import type { Article } from '@/components/dashboard/NewsCard'

const id = 'e133b1af-bd10-4fb6-ae61-558f89c8bd01'
const secondId = 'e133b1af-bd10-4fb6-ae61-558f89c8bd02'
const article: Article = { id, title: '합성은행', agency: 'FSS_SANCTION', category: 'sanction_notice', published_at: '2026-09-10', link: 'https://www.fss.or.kr/fss/notice', analysis_result: { summary: ['수집된 공개 요약'] } }
function payload(articleId = id, title = '담보 확인 누락') {
    return { enabled: true, reports: [{ id, article_id: articleId, published_at: '2026-09-10', source: { title: '합성은행', published_at: '2026-09-09', url: article.link }, report: { items: [{ finding_id: 'F1', title, summary: '공개 제재 요약 내용', departments: ['여신심사부'], related_work: '담보 평가 및 승인 관리', source_pages: [2], checks: [{ question: '최근 승인 건의 평가 기록을 확인했는가?', evidence_to_request: '승인 기록과 평가 보고서' }] }] } }] }
}
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('dashboard sanction deep report', () => {
    it('shows master version, inferred duty basis and question owners', async () => {
        const data = payload()
        Object.assign(data.reports[0].report, { analysis_basis: 'duty_master', master_version: 'fixture-v1', master_fingerprint: 'a'.repeat(64) })
        Object.assign(data.reports[0].report.items[0], { department_basis: [{ department: '여신심사부', duty_ids: ['HQ-001'], basis: 'inferred' }] })
        Object.assign(data.reports[0].report.items[0].checks[0], { department: '여신심사부' })
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(data)))
        render(<ReportModal isOpen article={article} onClose={() => {}} />)
        expect(await screen.findByText(/업무 귀속 추정/)).toBeInTheDocument()
        expect(screen.getByText(/fixture-v1/)).toBeInTheDocument()
        expect(screen.getByText(/영업조직은 대상에서 제외/)).toBeInTheDocument()
    })
    it('labels automatic reports without claiming administrator approval', async () => {
        const data = payload()
        Object.assign(data.reports[0], { publication_source: 'automatic' })
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(data)))
        render(<ReportModal isOpen article={article} onClose={() => {}} />)
        await screen.findByText('AI 자동 분석 · 담당자 확인 필요')
        expect(screen.queryByText('관리자 검토 완료')).not.toBeInTheDocument()
    })
    it('opens the per-article published briefing and bank checks without calling generation APIs', async () => {
        const fetchMock = vi.fn().mockResolvedValue(response(payload()))
        vi.stubGlobal('fetch', fetchMock)
        const close = vi.fn()
        render(<ReportModal isOpen article={article} onClose={close} />)
        expect(screen.getByRole('dialog', { name: '합성은행' })).toBeInTheDocument()
        await screen.findByText('여신심사부')
        expect(screen.getByText('제재공시 요약 브리핑')).toBeInTheDocument()
        expect(screen.getByText('소관업무')).toBeInTheDocument()
        expect(screen.getByText('담보 평가 및 승인 관리')).toBeInTheDocument()
        expect(screen.getByText('점검 포인트')).toBeInTheDocument()
        expect(screen.getByText('확인할 증빙: 승인 기록과 평가 보고서')).toBeInTheDocument()
        expect(fetchMock).toHaveBeenCalledTimes(1)
        expect(fetchMock.mock.calls[0][0]).toBe(`/api/sanction-publications?articleId=${id}`)
        expect(fetchMock.mock.calls[0][1].method).toBeUndefined()
        expect(screen.queryByText('내부 근거')).not.toBeInTheDocument()
        expect(screen.getByRole('link', { name: '점검표 Excel' })).toHaveAttribute('href', `/api/sanction-publications?id=${id}&format=xlsx`)
        fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
        expect(close).toHaveBeenCalledTimes(1)
    })
    it.each(['FSS_SANCTION','FSS_MGMT_NOTICE'])('shows public summary and honest unpublished state for %s', async agency => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ enabled: true, reports: [] })))
        render(<ReportModal isOpen article={{ ...article, agency }} onClose={() => {}} />)
        await screen.findByText(/아직 게시된 당행 관점 리포트가 없습니다/)
        expect(screen.getByText('수집된 공개 요약')).toBeInTheDocument()
        expect(screen.queryByText('여신심사부')).not.toBeInTheDocument()
    })
    it('never shows a previous article or a late response when switching cards', async () => {
        let resolve: (value: Response) => void = () => {}
        const pending = new Promise<Response>(r => { resolve = r })
        vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(pending).mockResolvedValueOnce(response(payload(secondId, '새 공시 지적사항'))))
        const { rerender } = render(<ReportModal isOpen article={article} onClose={() => {}} />)
        rerender(<ReportModal isOpen article={{ ...article, id: secondId, title: '새 은행' }} onClose={() => {}} />)
        await screen.findAllByText(/새 공시 지적사항/)
        await act(async () => { resolve(response(payload(id, '이전 공시 지적사항'))); await pending })
        expect(screen.queryByText(/이전 공시 지적사항/)).not.toBeInTheDocument()
        expect(within(screen.getByRole('dialog')).getByRole('heading', { name: '새 은행' })).toBeInTheDocument()
    })
    it('does not display a response for a different article', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(payload(secondId))))
        render(<ReportModal isOpen article={article} onClose={() => {}} />)
        await screen.findByRole('alert')
        expect(screen.queryByText('여신심사부')).not.toBeInTheDocument()
    })
    it('distinguishes failed requests, retries and login expiry', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response({}, 503)).mockResolvedValueOnce(response({}, 401)))
        render(<ReportModal isOpen article={article} onClose={() => {}} />)
        fireEvent.click(await screen.findByRole('button', { name: '다시 시도' }))
        expect(await screen.findByRole('link', { name: '다시 로그인' })).toHaveAttribute('href', '/login')
    })
    it('releases scroll lock and does not fetch when closed', () => {
        const fetchMock = vi.fn()
        vi.stubGlobal('fetch', fetchMock)
        render(<ReportModal isOpen={false} article={article} onClose={() => {}} />)
        expect(fetchMock).not.toHaveBeenCalled()
        expect(document.body.style.overflow).not.toBe('hidden')
    })
})
