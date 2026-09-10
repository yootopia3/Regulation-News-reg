'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

export default function AdminLogin() {
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)
    const router = useRouter()
    async function submit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        const form = new FormData(event.currentTarget)
        setBusy(true); setError('')
        try {
            const response = await fetch('/api/admin/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: form.get('email'), password: form.get('password') }) })
            if (!response.ok) { setError(response.status === 503 ? '관리자 문서 관리가 아직 설정되지 않았습니다.' : '로그인에 실패했습니다. 관리자 계정을 확인해주세요.'); return }
            router.replace('/admin/documents'); router.refresh()
        } catch { setError('연결에 실패했습니다. 다시 시도해주세요.') }
        finally { setBusy(false) }
    }
    return <main className="min-h-screen bg-slate-50 flex items-center justify-center p-6"><section className="w-full max-w-md bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
        <p className="text-sm font-semibold text-blue-800">MarketPulse-Reg</p><h1 className="text-2xl font-bold mt-2 text-slate-900">문서 관리자 로그인</h1>
        <p className="text-sm text-slate-600 mt-3">등록된 관리자 계정으로 내부 문서를 관리합니다.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
            <label className="block text-sm text-slate-800">이메일<input name="email" type="email" autoComplete="username" required className="block w-full border rounded-lg p-3 mt-1" /></label>
            <label className="block text-sm text-slate-800">비밀번호<input name="password" type="password" autoComplete="current-password" required className="block w-full border rounded-lg p-3 mt-1" /></label>
            {error && <p role="alert" className="text-red-700 text-sm">{error}</p>}
            <button disabled={busy} className="w-full rounded-lg bg-blue-900 text-white p-3 disabled:opacity-50">{busy ? '확인 중…' : '로그인'}</button>
        </form><Link href="/" className="block mt-5 text-sm text-blue-800">대시보드로 돌아가기</Link>
    </section></main>
}
