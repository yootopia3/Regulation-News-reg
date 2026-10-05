import { NextRequest } from 'next/server'
import { z } from 'zod'
import { AdminError, adminFailure, boundedJson, privateJson } from '@/lib/admin-auth'
import { boardContext, deletePost, parsePostForm, publicPost, readPost, savePost, validId } from '@/lib/board/server'
type Params = { params: Promise<{ id: string }> }
export const runtime = 'nodejs'
export async function GET(request: NextRequest, { params }: Params) {
    try {
        const context = await boardContext(request)
        return privateJson({ post: publicPost(await readPost(context, (await params).id)), isAdmin: context.isAdmin })
    } catch (error) { return adminFailure(error) }
}
export async function PATCH(request: NextRequest, { params }: Params) {
    try {
        const context = await boardContext(request)
        const id = validId((await params).id)
        const { input, files } = await parsePostForm(request)
        return privateJson({ post: await savePost(context, input, files, id) })
    } catch (error) { return adminFailure(error) }
}
export async function DELETE(request: NextRequest, { params }: Params) {
    try {
        const context = await boardContext(request)
        const parsed = z.object({ password: z.string().max(128).default(''), revision: z.number().int().nonnegative() }).strict().safeParse(await boundedJson(request, 2048))
        if (!parsed.success) throw new AdminError(400, 'invalid_request')
        await deletePost(context, (await params).id, parsed.data.password, parsed.data.revision)
        return privateJson({ ok: true })
    } catch (error) { return adminFailure(error) }
}
