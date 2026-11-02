import { createCipheriv, createDecipheriv, createHmac, randomBytes, timingSafeEqual } from 'node:crypto'
import { z } from 'zod'
import { AdminError, type adminClient } from '@/lib/admin-auth'
import { normalizeBase, providerRequest } from './network'
import type { ConnectionForm, ConnectionView } from './types'

type DB = ReturnType<typeof adminClient>
export type ConnectionRow = Omit<ConnectionForm, 'api_key'> & { api_key_ciphertext: string; key_last4: string; updated_at: string }
export const ConnectionInput = z.object({
    base_url: z.string().trim().min(8).max(500), protocol: z.enum(['responses', 'chat_completions']),
    model: z.string().trim().max(200).regex(/^[\x21-\x7e]*$/),
    api_key: z.string().trim().max(4096).regex(/^[\x21-\x7e]*$/), revision: z.number().int().nonnegative(),
}).strict()
const AAD = 'sanction-ai-connection:v1:'
export function encryptionKey() {
    const value = process.env.AI_CONNECTION_ENCRYPTION_KEY || ''
    if (process.env.SANCTION_AI_SETTINGS_ENABLED !== 'true' || !/^[a-fA-F0-9]{64}$/.test(value)) throw new AdminError(503, 'connection_not_configured')
    return Buffer.from(value, 'hex')
}
export function encryptKey(key: string, base: string) {
    const iv = randomBytes(12)
    const cipher = createCipheriv('aes-256-gcm', encryptionKey(), iv)
    cipher.setAAD(Buffer.from(AAD + base))
    const encrypted = Buffer.concat([cipher.update(key, 'utf8'), cipher.final()])
    return ['v1', iv.toString('base64'), cipher.getAuthTag().toString('base64'), encrypted.toString('base64')].join('.')
}
export function decryptKey(row: ConnectionRow) {
    try {
        const [version, iv, tag, value, extra] = row.api_key_ciphertext.split('.')
        if (version !== 'v1' || extra !== undefined) throw new Error()
        const decipher = createDecipheriv('aes-256-gcm', encryptionKey(), Buffer.from(iv, 'base64'))
        decipher.setAAD(Buffer.from(AAD + row.base_url)); decipher.setAuthTag(Buffer.from(tag, 'base64'))
        return Buffer.concat([decipher.update(Buffer.from(value, 'base64')), decipher.final()]).toString('utf8')
    } catch { throw new AdminError(503, 'connection_not_configured') }
}
export async function readConnection(db: DB): Promise<ConnectionRow | null> {
    encryptionKey()
    const { data, error } = await db.from('sanction_ai_connection').select('base_url,protocol,model,api_key_ciphertext,key_last4,revision,updated_at').eq('id', true).maybeSingle()
    if (error) throw new AdminError(503, 'connection_not_configured')
    return data as ConnectionRow | null
}
export function connectionView(row: ConnectionRow | null, available = true): ConnectionView {
    return { available, configured: !!row, base_url: row?.base_url || 'https://api.openai.com/v1',
        protocol: row?.protocol || 'responses', model: row?.model || '', key_last4: row?.key_last4 || '',
        revision: row?.revision || 0, updated_at: row?.updated_at || null }
}
export async function resolveInput(db: DB, value: unknown, requireModel = true) {
    const parsed = ConnectionInput.safeParse(value)
    if (!parsed.success || (requireModel && !parsed.data.model)) throw new AdminError(400, 'invalid_request')
    const input = { ...parsed.data, base_url: normalizeBase(parsed.data.base_url) }
    const row = await readConnection(db)
    if (input.revision !== (row?.revision || 0)) throw new AdminError(409, 'connection_conflict')
    if (!input.api_key) {
        if (!row || row.base_url !== input.base_url) throw new AdminError(400, 'connection_key_required')
        input.api_key = decryptKey(row)
    }
    if (input.api_key.length < 8) throw new AdminError(400, 'invalid_request')
    return input
}
function receiptMac(input: ConnectionForm, actor: string, expires: string) {
    return createHmac('sha256', encryptionKey()).update(JSON.stringify(['connection-test-v1', actor, expires, input.base_url,
        input.protocol, input.model, input.api_key, input.revision])).digest('base64url')
}
export function makeReceipt(input: ConnectionForm, actor: string) {
    const expires = String(Date.now() + 10 * 60 * 1000)
    return `${expires}.${receiptMac(input, actor, expires)}`
}
export function checkReceipt(input: ConnectionForm, actor: string, receipt: string) {
    const [expires, signature, extra] = receipt.split('.')
    const expected = receiptMac(input, actor, expires)
    if (extra !== undefined || !/^\d{13}$/.test(expires) || Number(expires) <= Date.now() || Number(expires) > Date.now() + 10 * 60 * 1000 ||
        !/^[A-Za-z0-9_-]{43}$/.test(signature || '') || !timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) throw new AdminError(400, 'connection_test_required')
}
export async function modelList(input: ConnectionForm) {
    const raw = await providerRequest(input.base_url, 'models', input.api_key)
    const parsed = z.object({ data: z.array(z.object({ id: z.string().min(1).max(200) })).max(10000) }).safeParse(raw)
    if (!parsed.success) throw new AdminError(502, 'invalid_response')
    return [...new Set(parsed.data.data.map(model => model.id))].sort().slice(0, 200)
}
export async function testConnection(input: ConnectionForm) {
    const instruction = 'Return exactly this JSON object: {"ok":true}. Do not include other text.'
    const schema = { type: 'object', properties: { ok: { type: 'boolean' } }, required: ['ok'], additionalProperties: false }
    const chat = input.protocol === 'chat_completions'
    const raw = await providerRequest(input.base_url, chat ? 'chat/completions' : 'responses', input.api_key, chat ? {
        model: input.model, max_tokens: 12000, stream: false, response_format: { type: 'json_object' },
        messages: [{ role: 'system', content: instruction }, { role: 'user', content: 'Connection test.' }],
    } : { model: input.model, store: false, background: false, max_output_tokens: 12000, truncation: 'disabled', instructions: instruction,
        input: [{ role: 'user', content: 'Connection test.' }],
        text: { format: { type: 'json_schema', name: 'ConnectionTest', strict: true, schema } } })
    try {
        let text: string
        if (chat) {
            const response = z.object({ choices: z.array(z.object({ finish_reason: z.literal('stop'), message: z.object({ content: z.string(), refusal: z.null().optional() }) })).length(1) }).parse(raw)
            text = response.choices[0].message.content
        } else {
            const response = z.object({ status: z.literal('completed'), output: z.array(z.object({ type: z.string(), content: z.array(z.object({ type: z.string(), text: z.string().optional() })).optional() })) }).parse(raw)
            const parts = response.output.filter(item => item.type === 'message').flatMap(item => item.content || [])
            if (parts.length !== 1 || parts[0].type !== 'output_text') throw new Error()
            text = parts[0].text || ''
        }
        z.object({ ok: z.literal(true) }).strict().parse(JSON.parse(text))
    } catch { throw new AdminError(502, 'invalid_response') }
}
export async function saveConnection(db: DB, input: ConnectionForm, actor: string, receipt: string) {
    checkReceipt(input, actor, receipt)
    const { data, error } = await db.rpc('sanction_ai_connection_save', { p_revision: input.revision,
        p_base_url: input.base_url, p_protocol: input.protocol, p_model: input.model,
        p_ciphertext: encryptKey(input.api_key, input.base_url), p_last4: input.api_key.slice(-4), p_actor: actor })
    if (error) throw new AdminError(error.code === '40001' ? 409 : 503, error.code === '40001' ? 'connection_conflict' : 'connection_not_configured')
    return { revision: data }
}
