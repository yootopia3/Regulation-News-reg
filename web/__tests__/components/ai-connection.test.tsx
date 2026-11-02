import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import Page from '@/app/admin/ai-connection/page'
const view = { available: true, configured: true, base_url: 'https://ai.test/v1', protocol: 'responses', model: 'fixture-model', revision: 1, key_last4: 'unit', updated_at: null }
const response = (value: object) => new Response(JSON.stringify(value))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
describe('AI connection editor', () => {
    it('masks stored keys, requires a fresh test after edits and clears new keys after saving', async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(response(url.endsWith('/test') ? { receipt: 'fixture-receipt' } : view)))
        vi.stubGlobal('fetch', fetchMock)
        render(<Page />)
        await screen.findByDisplayValue('fixture-model')
        const key = screen.getByLabelText('API 키')
        expect(key).toHaveValue(''); expect(key).toHaveAttribute('type', 'password')
        expect(screen.getByRole('button', { name: '설정 저장' })).toBeDisabled()
        fireEvent.click(screen.getByRole('button', { name: '연결 시험' }))
        await screen.findByText('연결 시험에 성공했습니다. 저장하면 다음 분석부터 적용됩니다.')
        expect(screen.getByRole('button', { name: '설정 저장' })).toBeEnabled()
        fireEvent.change(key, { target: { value: 'synthetic-replacement' } })
        expect(screen.getByRole('button', { name: '설정 저장' })).toBeDisabled()
        fireEvent.click(screen.getByRole('button', { name: '연결 시험' }))
        await screen.findByText('연결 시험에 성공했습니다. 저장하면 다음 분석부터 적용됩니다.')
        fireEvent.click(screen.getByRole('button', { name: '설정 저장' }))
        await screen.findByText('저장했습니다. 다음 제재공시 분석부터 새 설정을 사용합니다.')
        expect(key).toHaveValue('')
        const save = fetchMock.mock.calls.find(([url, init]) => url === '/api/admin/ai-connection' && init?.method === 'POST')!
        expect(JSON.parse(save[1].body)).toMatchObject({ receipt: 'fixture-receipt', input: { api_key: 'synthetic-replacement', revision: 1 } })
    })
    it('locks the editor until initial setup and renders bounded server errors', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ ...view, available: false })))
        render(<Page />)
        await waitFor(() => expect(screen.getByRole('button', { name: '연결 시험' })).toBeDisabled())
        expect(await screen.findByText(/최초 서버 설정이 필요합니다/)).toBeInTheDocument()
    })
    it('clears a newly typed key when the destination changes', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(view)))
        render(<Page />)
        await screen.findByDisplayValue('fixture-model')
        const key = screen.getByLabelText('API 키')
        fireEvent.change(key, { target: { value: 'synthetic-server-a' } })
        fireEvent.change(screen.getByDisplayValue(view.base_url), { target: { value: 'https://other.test/v1' } })
        expect(key).toHaveValue('')
        expect(screen.getByRole('button', { name: '설정 저장' })).toBeDisabled()
    })
})
