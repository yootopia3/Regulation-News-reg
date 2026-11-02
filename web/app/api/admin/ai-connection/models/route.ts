import type { NextRequest } from 'next/server'
import { requireAdmin, adminRateLimit, boundedJson, privateJson, adminFailure } from '@/lib/admin-auth'
import { resolveInput, modelList } from '@/lib/ai-connection/server'
export const runtime = 'nodejs'
export const maxDuration = 30
export async function POST(request: NextRequest) {
    try {
        const { db, userId } = await requireAdmin(request)
        await adminRateLimit(db, 'ai-connection-probe', userId, 20, 3600)
        return privateJson({ models: await modelList(await resolveInput(db, await boundedJson(request), false)) })
    } catch (error) { return adminFailure(error) }
}
