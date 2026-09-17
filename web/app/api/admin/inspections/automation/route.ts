import { createHash, timingSafeEqual } from 'node:crypto'
import { z } from 'zod'
import { AdminError, adminClient, adminFailure, boundedJson, privateJson } from '@/lib/admin-auth'
import { autoPublish } from '@/lib/inspection-automation'

export const maxDuration = 60
export async function POST(request: Request) {
    try {
        const secret = process.env.SANCTION_AUTOMATION_TOKEN
        const supplied = request.headers.get('authorization') || ''
        if (!secret || secret.length < 32 || !timingSafeEqual(createHash('sha256').update(supplied).digest(), createHash('sha256').update(`Bearer ${secret}`).digest())) {
            throw new AdminError(401, 'unauthorized')
        }
        if (process.env.SANCTION_AUTOMATION_ENABLED !== 'true' || process.env.SANCTION_PUBLICATIONS_ENABLED !== 'true') throw new AdminError(503, 'disabled')
        const input = z.object({ id: z.string().uuid() }).strict().safeParse(await boundedJson(request, 1024))
        if (!input.success) throw new AdminError(400, 'invalid_request')
        return privateJson({ status: await autoPublish(adminClient(), input.data.id) })
    } catch (error) { return adminFailure(error) }
}
