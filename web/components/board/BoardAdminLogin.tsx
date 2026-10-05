'use client'
import { useState } from 'react'
import { boardRequest, jsonRequest } from '@/lib/board/client'
export default function BoardAdminLogin({ onLogin }: { onLogin: () => void }) {
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)
    return <details className="mt-10 border-t border-slate-200 pt-5 text-sm">
        <summary className="cursor-pointer text-slate-500">관리자 로그인</summary>
        <form className="mt-4 max-w-sm space-y-3" onSubmit={async event => {
            event.preventDefault(); if (busy) return
            const form = new FormData(event.currentTarget); setBusy(true); setError('')
            try {
                await boardRequest('/api/admin/login', jsonRequest('POST', { email: form.get('email'), password: form.get('password'), scope: 'board' }))
                onLogin()
            } catch (error) { setError(error instanceof Error ? error.message : '로그인에 실패했습니다.') }
            finally { setBusy(false) }
        }}>
            <label className="block">이메일<input className="mt-1 block w-full rounded-lg border p-2" name="email" type="email" autoComplete="username" required /></label>
            <label className="block">관리자 비밀번호<input className="mt-1 block w-full rounded-lg border p-2" name="password" type="password" autoComplete="current-password" required /></label>
            {error && <p role="alert" className="text-red-700">{error}</p>}
            <button disabled={busy} className="rounded-lg bg-blue-900 px-4 py-2 text-white disabled:opacity-50">{busy ? '확인 중…' : '관리자 로그인'}</button>
        </form>
    </details>
}
