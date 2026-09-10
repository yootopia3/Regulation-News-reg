import type { NextRequest } from 'next/server'
import { AdminError, requireAdmin, privateJson, adminFailure, adminRateLimit } from '@/lib/admin-auth'
import { DOCUMENT_COLUMNS, uploadDocument } from '@/lib/internal-documents'

export const maxDuration = 60

export async function GET(request: NextRequest) {
    try {
        const { db } = await requireAdmin(request)
        const offset = Number(request.nextUrl.searchParams.get('offset') || '0')
        if (!Number.isSafeInteger(offset) || offset < 0) throw new AdminError(400, 'invalid_offset')
        const { data, error } = await db.from('internal_documents').select(DOCUMENT_COLUMNS).order('created_at', { ascending: false }).order('id').range(offset, offset + 49)
        if (error) throw new AdminError(500, 'request_failed')
        return privateJson({ documents: data, nextOffset: data?.length === 50 ? offset + 50 : null })
    } catch (error) { return adminFailure(error) }
}

export async function POST(request: NextRequest) {
    try {
        const { db, userId } = await requireAdmin(request)
        await adminRateLimit(db, 'document-upload', userId, 10, 3600)
        return privateJson({ id: await uploadDocument(db, userId, request) }, 202)
    } catch (error) { return adminFailure(error) }
}
