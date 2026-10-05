import { NextRequest, NextResponse } from 'next/server'
import { AdminError, PRIVATE_HEADERS, adminFailure } from '@/lib/admin-auth'
import { BOARD_BUCKET, boardContext, readPost, validId } from '@/lib/board/server'
export const runtime = 'nodejs'
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string; attachmentId: string }> }) {
    try {
        const context = await boardContext(request)
        const { id, attachmentId } = await params
        const post = await readPost(context, id)
        const file = post.attachments.find(item => item.id === validId(attachmentId))
        if (!file) throw new AdminError(404, 'not_found')
        const { data, error } = await context.db.storage.from(BOARD_BUCKET).download(file.path)
        if (error || !data) throw new AdminError(503, 'request_failed')
        const filename = encodeURIComponent(file.name).replace(/['()*]/g, character => `%${character.charCodeAt(0).toString(16)}`)
        return new NextResponse(data, { headers: { ...PRIVATE_HEADERS,
            'Content-Type': 'application/octet-stream', 'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': "default-src 'none'; sandbox",
            'Content-Disposition': `attachment; filename="document"; filename*=UTF-8''${filename}`,
        } })
    } catch (error) { return adminFailure(error) }
}
