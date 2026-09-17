import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { verifySession } from '@/lib/auth'
import { adminClient, PRIVATE_HEADERS } from '@/lib/admin-auth'
import { publishedReports } from '@/lib/publication-service'

export async function GET(request: NextRequest) {
    if (!await verifySession(request.cookies.get('mp_session')?.value)) return NextResponse.json({ error: 'unauthorized' }, { status: 401, headers: PRIVATE_HEADERS })
    const query = z.object({ offset: z.coerce.number().int().min(0).max(1000000), id: z.string().uuid().optional(), articleId: z.string().uuid().optional(), format: z.enum(['json','xlsx']) }).safeParse({
        offset: request.nextUrl.searchParams.get('offset') || 0, id: request.nextUrl.searchParams.get('id') || undefined, format: request.nextUrl.searchParams.get('format') || 'json',
        articleId: request.nextUrl.searchParams.get('articleId') || undefined,
    })
    if (!query.success || (query.data.format === 'xlsx' && !query.data.id)) return NextResponse.json({ error: 'invalid_request' }, { status: 400, headers: PRIVATE_HEADERS })
    if (process.env.SANCTION_PUBLICATIONS_ENABLED !== 'true') return NextResponse.json({ reports: [], enabled: false, nextOffset: null }, { status: query.data.format === 'xlsx' ? 404 : 200, headers: PRIVATE_HEADERS })
    try {
        const { offset, id, articleId, format } = query.data
        const reports = await publishedReports(adminClient(), id || articleId ? 0 : offset, id, articleId)
        if (format === 'xlsx') {
            if (!reports.length) return NextResponse.json({ error: 'not_found' }, { status: 404, headers: PRIVATE_HEADERS })
            const { reportWorkbook } = await import('@/lib/publication-export')
            return new NextResponse(await reportWorkbook(reports[0].report, reports[0].source, reports[0].publication_source === 'automatic'), { headers: { ...PRIVATE_HEADERS,
                'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'Content-Disposition': 'attachment; filename="sanction-inspection.xlsx"',
            } })
        }
        return NextResponse.json({ reports, enabled: true, nextOffset: !id && !articleId && reports.length === 20 ? offset+20 : null }, { headers: PRIVATE_HEADERS })
    } catch { return NextResponse.json({ error: 'reports_unavailable' }, { status: 503, headers: PRIVATE_HEADERS }) }
}
