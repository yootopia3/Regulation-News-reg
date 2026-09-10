'use client'

import { useEffect, useState } from 'react'
import { sanctionSources, type SanctionSource } from '@/lib/sanction-report'

type LoadState = 'loading' | 'ready' | 'error' | 'unauthorized'

export function useSanctionSources() {
    const [rows, setRows] = useState<SanctionSource[]>([])
    const [state, setState] = useState<LoadState>('loading')
    const [attempt, setAttempt] = useState(0)
    useEffect(() => {
        const controller = new AbortController()
        let active = true
        const timeout = setTimeout(() => controller.abort(), 20000)
        async function load() {
            try {
                const response = await fetch('/api/articles', { cache: 'no-store', signal: controller.signal })
                if (!active) return
                if (response.status === 401) { setState('unauthorized'); return }
                if (!response.ok) throw new Error('request_failed')
                const data = sanctionSources(await response.json())
                if (active) { setRows(data); setState('ready') }
            } catch { if (active) setState('error') }
            finally { clearTimeout(timeout) }
        }
        void load()
        return () => { active = false; clearTimeout(timeout); controller.abort() }
    }, [attempt])
    return { rows, state, reload: () => { setState('loading'); setAttempt(value => value + 1) } }
}
