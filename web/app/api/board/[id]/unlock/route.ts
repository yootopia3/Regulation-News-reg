import { NextRequest } from 'next/server'
import { z } from 'zod'
import { AdminError, adminFailure, boundedJson, privateJson } from '@/lib/admin-auth'
import { authorizePost, boardContext, publicPost } from '@/lib/board/server'
export const runtime = 'nodejs'
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
    try {
        const context = await boardContext(request)
        const parsed = z.object({ password: z.string().max(128).default('') }).strict().safeParse(await boundedJson(request, 2048))
        if (!parsed.success) throw new AdminError(400, 'invalid_request')
        return privateJson({ post: publicPost(await authorizePost(context, (await params).id, parsed.data.password)), isAdmin: context.isAdmin })
    } catch (error) { return adminFailure(error) }
}
