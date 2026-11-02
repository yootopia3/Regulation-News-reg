import type { NextRequest } from 'next/server'
import { z } from 'zod'
import { AdminError, requireAdmin, adminRateLimit, boundedJson, privateJson, adminFailure } from '@/lib/admin-auth'
import { readConnection, connectionView, resolveInput, saveConnection } from '@/lib/ai-connection/server'
export const runtime = 'nodejs'
export async function GET(request: NextRequest) {
    try {
        const { db } = await requireAdmin(request)
        if (process.env.SANCTION_AI_SETTINGS_ENABLED !== 'true') return privateJson(connectionView(null, false))
        return privateJson(connectionView(await readConnection(db)))
    } catch (error) { return adminFailure(error) }
}
export async function POST(request: NextRequest) {
    try {
        const { db, userId } = await requireAdmin(request)
        await adminRateLimit(db, 'ai-connection-save', userId, 20, 3600)
        const body = z.object({ input: z.unknown(), receipt: z.string().max(200) }).strict().safeParse(await boundedJson(request))
        if (!body.success) throw new AdminError(400, 'invalid_request')
        const input = await resolveInput(db, body.data.input)
        return privateJson(await saveConnection(db, input, userId, body.data.receipt))
    } catch (error) { return adminFailure(error) }
}
