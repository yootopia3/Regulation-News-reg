import { NextRequest } from 'next/server'
import { AdminError, adminFailure, boundedJson, privateJson } from '@/lib/admin-auth'
import { boardContext } from '@/lib/board/server'
import { ChangeComment, DeleteComment, changeComment, deleteComment } from '@/lib/board/comments-server'

type Params = { params: Promise<{ id: string; commentId: string }> }
export const runtime = 'nodejs'
export async function PATCH(request: NextRequest, { params }: Params) {
    try {
        const context = await boardContext(request)
        const parsed = ChangeComment.safeParse(await boundedJson(request))
        if (!parsed.success) throw new AdminError(400, 'invalid_comment')
        const { id, commentId } = await params
        return privateJson({ comment: await changeComment(context, id, commentId, parsed.data) })
    } catch (error) { return adminFailure(error) }
}
export async function DELETE(request: NextRequest, { params }: Params) {
    try {
        const context = await boardContext(request)
        const parsed = DeleteComment.safeParse(await boundedJson(request, 2048))
        if (!parsed.success) throw new AdminError(400, 'invalid_comment')
        const { id, commentId } = await params
        await deleteComment(context, id, commentId, parsed.data)
        return privateJson({ ok: true })
    } catch (error) { return adminFailure(error) }
}
