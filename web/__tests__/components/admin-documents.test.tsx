import React, { Suspense } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DocumentsPage from '@/app/admin/documents/page'
import ReviewPage from '@/app/admin/documents/[id]/page'

const { documentRequest } = vi.hoisted(() => ({ documentRequest: vi.fn() }))
vi.mock('@/lib/document-ui', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/document-ui')>(), documentRequest }))
beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('document management UI', () => {
    it('shows the empty state and supported upload format', async () => {
        documentRequest.mockResolvedValue({ documents: [], nextOffset: null })
        render(<DocumentsPage />)
        expect(await screen.findByText('등록된 문서가 없습니다.')).toBeInTheDocument()
        expect(screen.getByLabelText('HWP 파일 · 최대 2MB')).toHaveAttribute('accept', '.hwp,.HWP')
        expect(screen.getByText(/외부 AI 분석을 실행하지 않습니다/)).toBeInTheDocument()
    })
    it('prevents activation of unsaved department edits', async () => {
        documentRequest.mockResolvedValue({ document: { title: 'Synthetic document', status: 'review', revision: 3, warnings: [], warnings_acknowledged: true, error_code: null }, units: [{ article_key: '1', heading: 'Synthetic team', department: 'Synthetic team', body: 'Synthetic duty', start_paragraph: 1, end_paragraph: 2, reviewed: true }] })
        const user = userEvent.setup()
        const params = Promise.resolve({ id: 'fixture' })
        await act(async () => { render(<Suspense fallback={<p>Loading</p>}><ReviewPage params={params} /></Suspense>); await params })
        const activate = await screen.findByRole('button', { name: '저장된 검토로 활성화' })
        expect(activate).toBeEnabled()
        await user.type(screen.getByLabelText('소관부서 후보'), ' edited')
        expect(activate).toBeDisabled()
        expect(screen.getByLabelText('이 조문의 부서와 업무를 확인했습니다.')).not.toBeChecked()
        await user.click(screen.getByLabelText('이 조문의 부서와 업무를 확인했습니다.'))
        expect(activate).toBeDisabled()
        await user.click(screen.getByRole('button', { name: '검토 저장' }))
        await waitFor(() => expect(documentRequest).toHaveBeenCalledWith('/api/admin/documents/fixture', expect.objectContaining({ method: 'PATCH' })))
    })
})
