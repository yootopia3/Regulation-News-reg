'use client'
import Link from 'next/link'
import { useState } from 'react'
import { KeyRound, Settings2, PlugZap, CheckCircle2 } from 'lucide-react'
import { useConnection } from '@/lib/ai-connection/use-connection'
import { AI_PROTOCOLS, type AIProtocol } from '@/lib/ai-connection/types'

export default function AIConnectionPage() {
    const state = useConnection()
    const [visible, setVisible] = useState(false)
    const { form, view, busy } = state
    const inputClass = 'mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-3 text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100'
    return <main className="min-h-screen bg-slate-50 p-6 text-slate-900 md:p-10"><div className="mx-auto max-w-3xl">
        <nav className="flex flex-wrap gap-5 text-sm text-blue-900"><Link href="/">대시보드</Link><Link href="/admin/documents">내부 문서 관리</Link><Link href="/admin/inspections">제재공시 분석 관리</Link></nav>
        <div className="mt-8 flex items-center gap-3"><Settings2 aria-hidden="true" className="text-blue-800" /><h1 className="text-3xl font-bold">AI 연결 설정</h1></div>
        <p className="mt-3 text-slate-600">제재공시 AI 심층 보고서에 사용할 서버와 모델을 설정합니다.</p>
        <div className="mt-6 rounded-xl border border-blue-100 bg-blue-50 p-5 text-sm text-blue-950">
            <p className="font-semibold">{view?.configured ? '관리자 설정 사용' : '기존 서버 환경설정 사용'}</p>
            <p className="mt-2 leading-6">저장한 설정은 다음 분석부터 적용됩니다. 진행 중인 분석과 이미 게시된 보고서는 유지됩니다.</p>
            {view?.updated_at && <p className="mt-2 text-xs text-blue-800">마지막 변경: {new Date(view.updated_at).toLocaleString('ko-KR')}</p>}
        </div>
        {state.error && <p role="alert" className="mt-5 rounded-lg bg-red-50 p-4 text-sm text-red-800">{state.error}</p>}
        {state.notice && <p role="status" className="mt-5 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-900">{state.notice}</p>}
        {view && !view.available && <p className="mt-5 rounded-lg bg-amber-50 p-4 text-sm text-amber-900">최초 서버 설정이 필요합니다. 설정 저장소와 암호화 키를 준비한 뒤 사용할 수 있습니다.</p>}
        <form className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:p-8" onSubmit={event => { event.preventDefault(); void state.act('save'); setVisible(false) }}>
            <fieldset disabled={!!busy || !view?.available} className="space-y-6">
                <label className="block text-sm font-semibold">연결 주소
                    <input type="url" required maxLength={500} className={inputClass} value={form.base_url} onChange={e => state.change({ base_url: e.target.value })} placeholder="https://서버주소/v1" />
                    <span className="mt-2 block text-xs font-normal leading-5 text-slate-500">API 기본 주소를 입력하세요. 선택한 연결 방식에 맞는 요청 경로는 자동으로 붙습니다.</span>
                </label>
                <label className="block text-sm font-semibold">연결 방식
                    <select className={inputClass} value={form.protocol} onChange={e => state.change({ protocol: e.target.value as AIProtocol })}>
                        {Object.entries(AI_PROTOCOLS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                    </select>
                    <span className="mt-2 block text-xs font-normal text-slate-500">현재 OpenAI는 Responses, 사진과 같은 호환 서버는 Chat Completions를 선택하세요.</span>
                </label>
                <label className="block text-sm font-semibold">모델 이름
                    <input list="ai-model-list" required maxLength={200} className={inputClass} value={form.model} onChange={e => state.change({ model: e.target.value })} placeholder="서버에 등록된 모델 이름" />
                    <datalist id="ai-model-list">{state.models.map(model => <option key={model} value={model} />)}</datalist>
                    <span className="mt-2 block text-xs font-normal text-slate-500">서버에 등록된 이름 그대로 입력하세요. API 키 입력 후 모델 목록을 조회할 수 있습니다.</span>
                </label>
                <div><label htmlFor="ai-api-key" className="flex items-center gap-2 text-sm font-semibold"><KeyRound size={16} aria-hidden="true" />API 키</label>
                    <div className="flex items-center gap-3"><input id="ai-api-key" type={visible ? 'text' : 'password'} autoComplete="new-password" maxLength={4096} spellCheck={false} className={inputClass} value={form.api_key} onChange={e => state.change({ api_key: e.target.value })} placeholder={view?.key_last4 ? `변경할 때만 입력 · 현재 끝자리 ${view.key_last4}` : '이 서버에서 발급받은 API 키'} />
                        <button type="button" className="mt-2 shrink-0 text-sm text-blue-800" onClick={() => setVisible(!visible)}>{visible ? '숨기기' : '보기'}</button></div>
                    <p className="mt-2 text-xs leading-5 text-slate-500">저장된 키 전체는 표시하지 않습니다. 주소를 바꾸면 새 서버의 키도 입력해 주세요.</p>
                </div>
                <div className="flex flex-wrap gap-3 border-t border-slate-100 pt-6">
                    <button type="button" onClick={() => void state.act('models')} className="rounded-lg border border-slate-300 px-4 py-3 text-sm disabled:opacity-40">{busy === 'models' ? '조회 중…' : '모델 목록 조회'}</button>
                    <button type="button" disabled={!form.model.trim()} onClick={() => void state.act('test')} className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-900 disabled:opacity-40"><PlugZap size={16} aria-hidden="true" />{busy === 'test' ? '시험 중…' : '연결 시험'}</button>
                    <button type="submit" disabled={!state.receipt} className="ml-auto flex items-center gap-2 rounded-lg bg-blue-900 px-6 py-3 text-sm font-semibold text-white disabled:opacity-40"><CheckCircle2 size={16} aria-hidden="true" />{busy === 'save' ? '저장 중…' : '설정 저장'}</button>
                </div>
                <p className="text-xs leading-5 text-slate-500">연결 시험은 짧은 테스트 문장으로 응답을 확인하며 소량의 API 사용료가 발생할 수 있습니다. 시험 성공 후 저장할 수 있습니다.</p>
            </fieldset>
        </form>
        <div className="mt-5 flex items-start justify-between gap-5 text-xs leading-5 text-slate-500"><p>사내망 전용 서버를 사용하려면 웹 서버와 분석 프로그램도 해당 서버에 접속 가능한 환경에서 실행해야 합니다.</p><button type="button" disabled={!!busy} onClick={() => { void state.act('reload'); setVisible(false) }} className="shrink-0 text-blue-800 underline">설정 새로고침</button></div>
    </div></main>
}
