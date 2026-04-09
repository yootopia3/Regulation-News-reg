import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { NextRequest } from 'next/server'

vi.mock('@/lib/auth', () => ({
  verifySession: vi.fn(),
}))

import { proxy } from '@/proxy'
import { verifySession } from '@/lib/auth'

const verifySessionMock = vi.mocked(verifySession)

function makeRequest(url: string, sessionCookie?: string): NextRequest {
  const parsed = new URL(url)
  const cookieStore = new Map<string, { name: string; value: string }>()
  if (sessionCookie !== undefined) {
    cookieStore.set('mp_session', { name: 'mp_session', value: sessionCookie })
  }
  return {
    nextUrl: parsed,
    url: parsed.toString(),
    cookies: {
      get: (name: string) => cookieStore.get(name),
    },
  } as unknown as NextRequest
}

beforeEach(() => {
  verifySessionMock.mockReset()
})

describe('proxy', () => {
  describe('whitelist (verifySession not called)', () => {
    it('passes through /login', async () => {
      const res = await proxy(makeRequest('http://localhost/login'))
      expect(res.status).toBe(200)
      expect(verifySessionMock).not.toHaveBeenCalled()
    })

    it('passes through /api/auth/login', async () => {
      const res = await proxy(makeRequest('http://localhost/api/auth/login'))
      expect(res.status).toBe(200)
      expect(verifySessionMock).not.toHaveBeenCalled()
    })

    it('passes through /_next/static/chunks/main.js', async () => {
      const res = await proxy(makeRequest('http://localhost/_next/static/chunks/main.js'))
      expect(res.status).toBe(200)
      expect(verifySessionMock).not.toHaveBeenCalled()
    })

    it('passes through paths containing a dot (e.g. /favicon.ico)', async () => {
      const res = await proxy(makeRequest('http://localhost/favicon.ico'))
      expect(res.status).toBe(200)
      expect(verifySessionMock).not.toHaveBeenCalled()
    })
  })

  describe('auth failure', () => {
    it('returns 401 JSON for /api/* when verifySession returns null', async () => {
      verifySessionMock.mockResolvedValue(null)
      const res = await proxy(makeRequest('http://localhost/api/x'))
      expect(res.status).toBe(401)
      const body = await res.json()
      expect(body).toEqual({ error: 'unauthorized' })
    })

    it('redirects (307) to /login for non-API routes when verifySession returns null', async () => {
      verifySessionMock.mockResolvedValue(null)
      const res = await proxy(makeRequest('http://localhost/dashboard'))
      expect(res.status).toBe(307)
      const location = res.headers.get('location')
      expect(location).not.toBeNull()
      expect(location!.endsWith('/login')).toBe(true)
    })
  })

  describe('auth success', () => {
    it('passes through /dashboard when verifySession returns a payload', async () => {
      verifySessionMock.mockResolvedValue({ iat: 1, exp: 9999999999 })
      const res = await proxy(makeRequest('http://localhost/dashboard', 'cookie-value'))
      expect(res.status).toBe(200)
      expect(verifySessionMock).toHaveBeenCalledWith('cookie-value')
    })
  })
})
