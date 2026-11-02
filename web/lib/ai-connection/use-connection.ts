'use client'
import { useEffect, useState } from 'react'
import { connectionRequest, type ConnectionForm, type ConnectionView } from './types'

export function useConnection() {
    const [view, setView] = useState<ConnectionView | null>(null)
    const [form, setForm] = useState<ConnectionForm>({ base_url: 'https://api.openai.com/v1', protocol: 'responses', model: '', api_key: '', revision: 0 })
    const [models, setModels] = useState<string[]>([])
    const [receipt, setReceipt] = useState('')
    const [busy, setBusy] = useState('loading')
    const [error, setError] = useState('')
    const [notice, setNotice] = useState('')
    async function load() {
        const data: ConnectionView = await connectionRequest('')
        setView(data); setForm({ base_url: data.base_url, protocol: data.protocol, model: data.model, api_key: '', revision: data.revision })
        setReceipt(''); setModels([])
    }
    useEffect(() => { let alive = true
        connectionRequest('').then((data: ConnectionView) => { if (alive) {
            setView(data); setForm({ base_url: data.base_url, protocol: data.protocol, model: data.model, api_key: '', revision: data.revision })
        } }).catch(e => { if (alive) setError(e.message) }).finally(() => { if (alive) setBusy('') })
        return () => { alive = false }
    }, [])
    function change(patch: Partial<ConnectionForm>) {
        setForm(previous => ({ ...previous, ...patch, ...('base_url' in patch ? { api_key: '' } : {}) })); setReceipt(''); setNotice(''); setError('')
        if ('base_url' in patch) setModels([])
    }
    async function act(action: 'models' | 'test' | 'save' | 'reload') {
        setBusy(action); setError(''); setNotice('')
        try {
            if (action === 'reload') await load()
            else if (action === 'models') {
                const data = await connectionRequest('/models', form); setModels(data.models)
                setNotice(data.models.length ? '모델 목록을 불러왔습니다. 모델 이름 입력란에서 선택하거나 직접 입력하세요.' : '조회된 모델이 없습니다. 모델 이름을 직접 입력한 뒤 연결 시험을 진행하세요.')
            } else if (action === 'test') {
                setReceipt('')
                const data = await connectionRequest('/test', form); setReceipt(data.receipt)
                setNotice('연결 시험에 성공했습니다. 저장하면 다음 분석부터 적용됩니다.')
            } else {
                await connectionRequest('', { input: form, receipt }); await load()
                setNotice('저장했습니다. 다음 제재공시 분석부터 새 설정을 사용합니다.')
            }
        } catch (e) { setError((e as Error).message) }
        finally { setBusy('') }
    }
    return { view, form, models, receipt, busy, error, notice, change, act }
}
