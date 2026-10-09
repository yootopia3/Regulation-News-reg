import { NextRequest } from 'next/server'
import { AdminError, adminFailure, boundedJson, privateJson } from '@/lib/admin-auth'
import { boardContext } from '@/lib/board/server'
import { CreateComment, createComment, listComments } from '@/lib/board/comments-server'

type Params = { params: Promise<{ id: string }> }
export const runtime = 'nodejs'
export async function GET(request: NextRequest, { params }: Params) {
    try {
        const context = await boardContext(request)
        return privateJson(await listComments(context, (await params).id, request.nextUrl.searchParams))
    } catch (error) { return adminFailure(error) }
}
export async function POST(request: NextRequest, { params }: Params) {
    try {
        const context = await boardContext(request)
        const parsed = CreateComment.safeParse(await boundedJson(request))
        if (!parsed.success) throw new AdminError(400, 'invalid_comment')
        return privateJson({ comment: await createComment(context, (await params).id, parsed.data) }, 201)
    } catch (error) { return adminFailure(error) }
}
