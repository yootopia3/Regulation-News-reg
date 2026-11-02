// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EventEmitter } from 'node:events'
const { lookup, send, wire } = vi.hoisted(() => ({ lookup: vi.fn(), send: vi.fn(), wire: { status: 200, body: '{}' } }))
vi.mock('node:dns/promises', () => ({ lookup }))
vi.mock('node:https', () => ({ request: send }))
vi.mock('node:http', () => ({ request: send }))
import { allowedAddress, normalizeBase, resolveDestination, providerRequest } from '@/lib/ai-connection/network'
beforeEach(() => {
    vi.clearAllMocks(); wire.status = 200; wire.body = '{}'
    lookup.mockResolvedValue([{ address: '8.8.8.8', family: 4 }])
    send.mockImplementation((_url, _options, callback) => {
        const request = new EventEmitter() as EventEmitter & { end: (payload: unknown) => void }
        request.end = () => {
            const response = Object.assign(new EventEmitter(), { statusCode: wire.status, destroy: vi.fn() })
            callback(response)
            response.emit('data', Buffer.from(wire.body)); response.emit('end')
        }
        return request
    })
})
afterEach(() => { vi.unstubAllEnvs() })
describe('AI destination boundary', () => {
    it.each(['http://example.test/v1','https://user:pass@example.test/v1','https://example.test/v1?key=x','https://example.test/v1#x','https://example.test/v1%2fmodels','https://example.test/v1/chat/completions','https://example.test./v1'])('rejects unsafe/malformed base %s', base => {
        expect(() => normalizeBase(base)).toThrow('unsafe_ai_url')
    })
    it.each(['127.0.0.1','0.0.0.0','169.254.169.254','100.64.0.1','192.168.1.1','10.0.0.1','172.20.0.1','224.0.0.1','::1','::ffff:127.0.0.1','fe80::1','fc00::1','2001:db8::1','2002:7f00:1::'])('blocks non-public destination %s', async address => {
        expect(allowedAddress(address, false)).toBe(false)
        lookup.mockResolvedValue([{ address, family: address.includes(':') ? 6 : 4 }])
        await expect(providerRequest('https://ai.example.test/v1', 'models', 'fixture')).rejects.toThrow('unsafe_ai_url')
        expect(send).not.toHaveBeenCalled()
    })
    it('rejects mixed DNS answers, pins one checked public address and keeps the original TLS host', async () => {
        lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }, { address: '127.0.0.1', family: 4 }])
        await expect(resolveDestination('https://ai.example.test/v1')).rejects.toThrow('unsafe_ai_url')
        await providerRequest('https://ai.example.test/v1', 'responses', 'synthetic', { model: 'fixture' })
        const [url, options] = send.mock.calls[0]
        expect(url.href).toBe('https://ai.example.test/v1/responses')
        const callback = vi.fn(); options.lookup(url.hostname, {}, callback)
        expect(callback).toHaveBeenCalledWith(null, '8.8.8.8', 4)
        expect(options.autoSelectFamily).toBe(false); expect(options.signal).toBeDefined()
        expect(options.headers.Authorization).toBe('Bearer synthetic')
    })
    it('permits only an explicitly allowed private base; metadata and loopback remain blocked', async () => {
        vi.stubEnv('AI_CONNECTION_PRIVATE_BASE_URLS', 'http://ai.company.test:8000/v1')
        lookup.mockResolvedValue([{ address: '10.0.0.8', family: 4 }])
        expect((await resolveDestination('http://ai.company.test:8000/v1')).address).toBe('10.0.0.8')
        await expect(resolveDestination('http://other.company.test:8000/v1')).rejects.toThrow('unsafe_ai_url')
        for (const address of ['127.0.0.1', '169.254.169.254', '8.8.8.8']) {
            lookup.mockResolvedValue([{ address, family: 4 }])
            await expect(resolveDestination('http://ai.company.test:8000/v1')).rejects.toThrow('unsafe_ai_url')
        }
    })
    it('rejects redirects, oversized bodies and malformed JSON without leaking provider text', async () => {
        wire.status = 302; wire.body = 'PRIVATE_CANARY'
        await expect(providerRequest('https://ai.test/v1','models','synthetic')).rejects.toThrow('provider_failed')
        expect(send).toHaveBeenCalledTimes(1)
        wire.status = 200; wire.body = 'x'.repeat(1024 * 1024 + 1)
        await expect(providerRequest('https://ai.test/v1','models','synthetic')).rejects.toThrow('response_limit')
        wire.body = 'PRIVATE_CANARY'
        await expect(providerRequest('https://ai.test/v1','models','synthetic')).rejects.toThrow('invalid_response')
    })
})
