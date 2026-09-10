import type { NextRequest } from 'next/server'
import { AdminError, requireAdmin, privateJson, adminFailure, boundedJson } from '@/lib/admin-auth'
import { DocumentAction, DocumentId, getDocument } from '@/lib/internal-documents'

type Context = { params: Promise<{ id: string }> }
export async function GET(request: NextRequest, context: Context) {
    try {
        const { db } = await requireAdmin(request)
        const id = DocumentId.safeParse((await context.params).id)
        if (!id.success) throw new AdminError(400, 'invalid_id')
        return privateJson(await getDocument(db, id.data))
    } catch (error) { return adminFailure(error) }
}

export async function PATCH(request: NextRequest, context: Context) {
    try {
        const { db, userId } = await requireAdmin(request)
        const id = DocumentId.safeParse((await context.params).id)
        const action = DocumentAction.safeParse(await boundedJson(request, 256 * 1024))
        if (!id.success || !action.success) throw new AdminError(400, 'invalid_input')
        const { data, error } = await db.rpc('internal_document_action', { p_id: id.data, p_actor: userId, p_input: action.data })
        if (error) throw new AdminError(error.code === 'P0001' ? 409 : 500, error.code === 'P0001' ? 'state_conflict' : 'request_failed')
        return privateJson({ ok: true, revision: data })
    } catch (error) { return adminFailure(error) }
}
