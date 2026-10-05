import { NextRequest } from 'next/server'
import { adminFailure, privateJson } from '@/lib/admin-auth'
import { boardContext, listPosts, parsePostForm, savePost } from '@/lib/board/server'
export const runtime = 'nodejs'
export async function GET(request: NextRequest) {
    try { return privateJson(await listPosts(await boardContext(request), request.nextUrl.searchParams)) }
    catch (error) { return adminFailure(error) }
}
export async function POST(request: NextRequest) {
    try {
        const context = await boardContext(request)
        const { input, files } = await parsePostForm(request)
        return privateJson({ post: await savePost(context, input, files) }, 201)
    } catch (error) { return adminFailure(error) }
}
