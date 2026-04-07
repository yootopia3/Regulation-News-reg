export type SessionPayload = { iat: number; exp: number }

const encoder = new TextEncoder()

function base64urlEncode(bytes: Uint8Array): string {
    let binary = ''
    for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function base64urlDecode(input: string): Uint8Array {
    const padded = input.replace(/-/g, '+').replace(/_/g, '/')
    const padLen = (4 - (padded.length % 4)) % 4
    const b64 = padded + '='.repeat(padLen)
    const binary = atob(b64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i)
    }
    return bytes
}

async function importHmacKey(secret: string): Promise<CryptoKey> {
    return crypto.subtle.importKey(
        'raw',
        encoder.encode(secret),
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['sign', 'verify']
    )
}

function timingSafeEqualBytes(a: Uint8Array, b: Uint8Array): boolean {
    if (a.length !== b.length) return false
    let diff = 0
    for (let i = 0; i < a.length; i++) {
        diff |= a[i] ^ b[i]
    }
    return diff === 0
}

export async function signSession(payload: SessionPayload): Promise<string> {
    const secret = process.env.SESSION_SECRET
    if (!secret) {
        throw new Error('SESSION_SECRET not set')
    }
    const payloadJson = JSON.stringify({ iat: payload.iat, exp: payload.exp })
    const payloadBytes = encoder.encode(payloadJson)
    const payloadSegment = base64urlEncode(payloadBytes)

    const key = await importHmacKey(secret)
    const signatureBuffer = await crypto.subtle.sign('HMAC', key, encoder.encode(payloadSegment))
    const signatureSegment = base64urlEncode(new Uint8Array(signatureBuffer))

    return `${payloadSegment}.${signatureSegment}`
}

export async function verifySession(token: string | undefined): Promise<SessionPayload | null> {
    const secret = process.env.SESSION_SECRET
    if (!secret) return null
    if (!token) return null

    const parts = token.split('.')
    if (parts.length !== 2) return null
    const [payloadSegment, signatureSegment] = parts
    if (!payloadSegment || !signatureSegment) return null

    let providedSig: Uint8Array
    try {
        providedSig = base64urlDecode(signatureSegment)
    } catch {
        return null
    }

    let expectedSigBuffer: ArrayBuffer
    try {
        const key = await importHmacKey(secret)
        expectedSigBuffer = await crypto.subtle.sign('HMAC', key, encoder.encode(payloadSegment))
    } catch {
        return null
    }
    const expectedSig = new Uint8Array(expectedSigBuffer)

    if (!timingSafeEqualBytes(expectedSig, providedSig)) return null

    let payload: SessionPayload
    try {
        const payloadBytes = base64urlDecode(payloadSegment)
        const payloadJson = new TextDecoder().decode(payloadBytes)
        const parsed = JSON.parse(payloadJson)
        if (
            typeof parsed !== 'object' ||
            parsed === null ||
            typeof parsed.iat !== 'number' ||
            typeof parsed.exp !== 'number'
        ) {
            return null
        }
        payload = { iat: parsed.iat, exp: parsed.exp }
    } catch {
        return null
    }

    if (payload.exp <= Math.floor(Date.now() / 1000)) return null

    return payload
}
