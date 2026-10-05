import { BOARD_ERRORS } from './types'
export async function boardRequest<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, { cache: 'no-store', ...init })
    const result = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(BOARD_ERRORS[result.error] || BOARD_ERRORS.request_failed)
    return result as T
}
export function jsonRequest(method: string, body: unknown): RequestInit {
    return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}
export function boardDate(value: string | null) {
    return value ? new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', dateStyle: 'medium' }).format(new Date(value)) : '임시저장'
}
