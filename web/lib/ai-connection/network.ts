import { lookup } from 'node:dns/promises'
import { BlockList, isIP } from 'node:net'
import { request as httpsRequest } from 'node:https'
import { request as httpRequest, type RequestOptions } from 'node:http'
import { AdminError } from '@/lib/admin-auth'

const blocked = new BlockList()
for (const [ip, bits] of [['0.0.0.0',8],['10.0.0.0',8],['100.64.0.0',10],['127.0.0.0',8],['169.254.0.0',16],['172.16.0.0',12],['192.0.0.0',24],['192.0.2.0',24],['192.88.99.0',24],['192.168.0.0',16],['198.18.0.0',15],['198.51.100.0',24],['203.0.113.0',24],['224.0.0.0',4],['240.0.0.0',4]] as const) blocked.addSubnet(ip, bits, 'ipv4')
for (const [ip, bits] of [['2001::',23],['2001:db8::',32],['2002::',16],['3fff::',20]] as const) blocked.addSubnet(ip, bits, 'ipv6')
const globalV6 = new BlockList(); globalV6.addSubnet('2000::', 3, 'ipv6')
const lan = new BlockList()
lan.addSubnet('10.0.0.0',8); lan.addSubnet('172.16.0.0',12); lan.addSubnet('192.168.0.0',16); lan.addSubnet('fc00::',7,'ipv6')

export function privateAllowed(base: string) {
    return (process.env.AI_CONNECTION_PRIVATE_BASE_URLS || '').split(',').map(s => s.trim().replace(/\/+$/, '')).includes(base)
}
export function normalizeBase(value: string) {
    try {
        if (!value || /[\s\\%]/.test(value)) throw new Error()
        const url = new URL(value)
        if (url.username || url.password || url.search || url.hash || !url.hostname || url.hostname.endsWith('.')) throw new Error()
        // Only simple base paths; never accept a completed operation URL.
        if (!/^\/[A-Za-z0-9/_-]*$/.test(url.pathname) || /\/(responses|models|chat\/completions)\/?$/.test(url.pathname)) throw new Error()
        const base = url.toString().replace(/\/+$/, '')
        if (url.protocol !== 'https:' && !(url.protocol === 'http:' && privateAllowed(base))) throw new Error()
        return base
    } catch { throw new AdminError(400, 'unsafe_ai_url') }
}
export function allowedAddress(address: string, privateBase: boolean) {
    const family = isIP(address)
    if (!family) return false
    const type = family === 6 ? 'ipv6' : 'ipv4'
    if (privateBase && lan.check(address, type)) return true
    return (family === 4 || globalV6.check(address, type)) && !blocked.check(address, type)
}
export async function resolveDestination(base: string) {
    const normalized = normalizeBase(base)
    const url = new URL(normalized)
    const host = url.hostname.replace(/^\[|\]$/g, '')
    let addresses
    try { addresses = await lookup(host, { all: true, verbatim: true }) }
    catch { throw new AdminError(502, 'provider_failed') }
    if (!addresses.length || addresses.some(a => !allowedAddress(a.address, privateAllowed(normalized)))) throw new AdminError(400, 'unsafe_ai_url')
    // Plain HTTP is permitted only to an explicitly allowed LAN endpoint.
    if (url.protocol === 'http:' && addresses.some(a => !lan.check(a.address, a.family === 6 ? 'ipv6' : 'ipv4'))) throw new AdminError(400, 'unsafe_ai_url')
    return { base: normalized, ...addresses[0] }
}

export async function providerRequest(base: string, path: 'models' | 'responses' | 'chat/completions', key: string, body?: object): Promise<unknown> {
    const destination = await resolveDestination(base)
    const url = new URL(`${destination.base}/${path}`)
    const payload = body ? JSON.stringify(body) : undefined
    return new Promise((resolve, reject) => {
        const fail = (code: string, status = 502) => reject(new AdminError(status, code))
        const options: RequestOptions & { autoSelectFamily: boolean } = {
            method: body ? 'POST' : 'GET', agent: false, autoSelectFamily: false,
            // Pin the checked address; TLS SNI and certificate verification retain the original hostname.
            lookup: (_host, _options, callback) => callback(null, destination.address, destination.family),
            signal: AbortSignal.timeout(20000),
            headers: { Authorization: `Bearer ${key}`, Accept: 'application/json', 'Accept-Encoding': 'identity',
                ...(payload ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) } : {}) },
        }
        const request = (url.protocol === 'https:' ? httpsRequest : httpRequest)(url, options, response => {
            if (response.statusCode !== 200) {
                const status = response.statusCode
                response.destroy()
                fail(status === 401 || status === 403 ? 'provider_auth_failed' : status === 429 ? 'rate_limited' : 'provider_failed')
                return
            }
            const chunks: Buffer[] = []; let size = 0
            response.on('data', (chunk: Buffer) => {
                size += chunk.length
                if (size > 1024 * 1024) { response.destroy(); fail('response_limit'); return }
                chunks.push(chunk)
            })
            response.on('error', () => fail('provider_failed'))
            response.on('end', () => {
                try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))) }
                catch { fail('invalid_response') }
            })
        })
        request.on('error', () => fail('provider_failed'))
        request.end(payload)
    })
}
