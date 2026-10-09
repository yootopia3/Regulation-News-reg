import { randomUUID } from 'node:crypto'
import { z } from 'zod'
import { AdminError, adminRateLimit } from '@/lib/admin-auth'
import { passwordSchema, readPost, validId, type BoardContext } from './server'
import { hashBoardPassword, verifyBoardPassword } from './password'
import { BOARD_COMMENT_PAGE_SIZE, MAX_COMMENT_BODY_LENGTH, type BoardComment } from './types'

export const COMMENT_COLUMNS = 'id,post_id,author_name,body,revision,created_at,updated_at'
const CommentBody = z.string().trim().min(1).max(MAX_COMMENT_BODY_LENGTH)
export const CreateComment = z.object({ author_name: z.string().trim().min(1).max(40), body: CommentBody, password: passwordSchema }).strict()
export const ChangeComment = z.object({ body: CommentBody, password: z.string().max(128).default(''), revision: z.number().int().nonnegative() }).strict()
export const DeleteComment = z.object({ password: z.string().max(128).default(''), revision: z.number().int().nonnegative() }).strict()

function publicComment(value: BoardComment): BoardComment {
    return { id: value.id, post_id: value.post_id, author_name: value.author_name, body: value.body,
        revision: value.revision, created_at: value.created_at, updated_at: value.updated_at }
}
async function publishedPost(context: BoardContext, postId: string) {
    const post = await readPost(context, validId(postId))
    if (post.status !== 'published') throw new AdminError(404, 'not_found')
}
function writeError(code?: string) {
    if (code === '23514' || code === '23503') throw new AdminError(404, 'not_found')
    throw new AdminError(503, 'request_failed')
}
export async function listComments(context: BoardContext, postId: string, params: URLSearchParams) {
    await publishedPost(context, postId)
    const page = z.coerce.number().int().min(1).max(5000).safeParse(params.get('page') || 1)
    if (!page.success) throw new AdminError(400, 'invalid_comment')
    const { data, count, error } = await context.db.from('board_comments').select(`${COMMENT_COLUMNS},board_posts!inner(status)`, { count: 'exact' })
        .eq('post_id', postId).eq('board_posts.status', 'published').order('created_at', { ascending: false }).order('id', { ascending: false })
        .range((page.data - 1) * BOARD_COMMENT_PAGE_SIZE, page.data * BOARD_COMMENT_PAGE_SIZE - 1)
    if (error) throw new AdminError(503, 'not_configured')
    return { comments: (data || []).map(row => publicComment(row as BoardComment)), total: count || 0, page: page.data, isAdmin: context.isAdmin }
}
export async function createComment(context: BoardContext, postId: string, input: z.infer<typeof CreateComment>) {
    await publishedPost(context, postId)
    const { data, error } = await context.db.from('board_comments').insert({ id: randomUUID(), post_id: postId,
        author_name: input.author_name, body: input.body, password_hash: await hashBoardPassword(input.password) }).select(COMMENT_COLUMNS).single()
    if (error) writeError(error.code)
    if (!data) throw new AdminError(503, 'request_failed')
    return publicComment(data as BoardComment)
}
async function authorizeComment(context: BoardContext, postId: string, commentId: string, password: string) {
    await publishedPost(context, postId)
    validId(commentId)
    if (!context.isAdmin) {
        if (!passwordSchema.safeParse(password).success) throw new AdminError(403, 'invalid_comment_password')
        await adminRateLimit(context.db, 'board-comment-password', commentId, 10, 900, 'board_rate_limit')
    }
    const { data, error } = await context.db.from('board_comments').select(`${COMMENT_COLUMNS},password_hash`)
        .eq('post_id', postId).eq('id', commentId).maybeSingle()
    if (error) throw new AdminError(503, 'request_failed')
    if (!data) throw new AdminError(404, 'comment_not_found')
    if (!context.isAdmin && !await verifyBoardPassword(password, data.password_hash)) throw new AdminError(403, 'invalid_comment_password')
    return data as BoardComment
}
export async function changeComment(context: BoardContext, postId: string, commentId: string, input: z.infer<typeof ChangeComment>) {
    const previous = await authorizeComment(context, postId, commentId, input.password)
    if (previous.revision !== input.revision) throw new AdminError(409, 'conflict')
    const { data, error } = await context.db.from('board_comments').update({ body: input.body,
        revision: previous.revision + 1, updated_at: new Date().toISOString() })
        .eq('post_id', postId).eq('id', commentId).eq('revision', previous.revision).select(COMMENT_COLUMNS).maybeSingle()
    if (error) writeError(error.code)
    if (!data) throw new AdminError(409, 'conflict')
    return publicComment(data as BoardComment)
}
export async function deleteComment(context: BoardContext, postId: string, commentId: string, input: z.infer<typeof DeleteComment>) {
    const previous = await authorizeComment(context, postId, commentId, input.password)
    if (previous.revision !== input.revision) throw new AdminError(409, 'conflict')
    const { data, error } = await context.db.from('board_comments').delete().eq('post_id', postId)
        .eq('id', commentId).eq('revision', previous.revision).select('id').maybeSingle()
    if (error) writeError(error.code)
    if (!data) throw new AdminError(409, 'conflict')
}
