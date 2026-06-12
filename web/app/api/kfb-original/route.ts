import { NextRequest, NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const KFB_BASE_LIST_URLS = [
    'http://m.kfb.or.kr/news/info_news.php',
    'http://www.kfb.or.kr/news/info_news.php',
    'https://www.kfb.or.kr/news/info_news.php',
    'https://m.kfb.or.kr/news/info_news.php',
]

const LINK_RE = /(?:href|src)\s*=\s*["']([^"']+)["']|(?:onclick)\s*=\s*["']([^"']+)["']|["']([^"']*(?:\.pdf|download|file=|down|info_news)[^"']*)["']/gi
const ROW_RE = /<(tr|li|div)\b[\s\S]*?<\/\1>/gi
const KFB_TITLE_META_RE = /\s+\d{4}[./-]\d{2}[./-]\d{2}(?:\s+\d+)?\s*$/
const KFB_DETAIL_ID_RE = /info_news_view\.php[^"']*?[?&]idx=(\d{2,})|(?:go|fnc?|open)?(?:view|detail|read)\w*\s*\(\s*['"]?(\d{2,})|(?:idx|num|no|seq|sn|board_no|article_no)\b\D{0,20}(\d{2,})/gi
const KFB_DETAIL_QUERY = 'col=&sw=&pg=1&gubun=&orderby=&code=&data_year=&SearchOffice=&SearchOpinion=&cate_idx=&BankAll='

function normalizeTitle(value: string): string {
    return decodeEntities(value)
        .replace(/<script\b[\s\S]*?<\/script>/gi, ' ')
        .replace(/<style\b[\s\S]*?<\/style>/gi, ' ')
        .replace(/<[^>]+>/g, ' ')
        .replace(KFB_TITLE_META_RE, '')
        .replace(/\s+/g, '')
        .trim()
}

function decodeEntities(value: string): string {
    return value
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)))
}

function countHangul(value: string): number {
    return value.match(/[가-힣]/g)?.length ?? 0
}

function decodeHtml(buffer: ArrayBuffer, contentType: string | null): string {
    const bytes = new Uint8Array(buffer)
    const charset = contentType?.match(/charset=([^;]+)/i)?.[1]?.trim().toLowerCase()
    const candidates = [charset, 'euc-kr', 'utf-8'].filter((value): value is string => Boolean(value))

    let best = ''
    for (const candidate of candidates) {
        try {
            const decoded = new TextDecoder(candidate).decode(bytes)
            if (countHangul(decoded) > countHangul(best)) best = decoded
        } catch {
            // Keep trying the remaining encodings.
        }
    }

    return best || new TextDecoder().decode(bytes)
}

async function fetchHtml(url: string): Promise<string | null> {
    try {
        const response = await fetch(url, {
            cache: 'no-store',
            headers: {
                'User-Agent':
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36',
            },
        })
        if (!response.ok) return null
        return decodeHtml(await response.arrayBuffer(), response.headers.get('content-type'))
    } catch (error) {
        console.warn('[KFB original] Failed to fetch', url, error)
        return null
    }
}

function resolveUrl(rawUrl: string, baseUrl: string): string | null {
    const cleaned = decodeEntities(rawUrl).trim()
    if (!cleaned || cleaned === '#') return null
    if (/^javascript:/i.test(cleaned)) return null

    try {
        return new URL(cleaned, baseUrl).toString()
    } catch {
        return null
    }
}

function findLinks(html: string, baseUrl: string): string[] {
    const links: string[] = []
    for (const match of html.matchAll(LINK_RE)) {
        const raw = match[1] || match[2] || match[3]
        if (!raw) continue

        const directUrl = resolveUrl(raw, baseUrl)
        if (directUrl) {
            links.push(directUrl)
            continue
        }

        const innerUrl = raw.match(/["']([^"']+\.(?:php|pdf)(?:\?[^"']*)?)["']/i)?.[1]
        if (innerUrl) {
            const resolved = resolveUrl(innerUrl, baseUrl)
            if (resolved) links.push(resolved)
        }
    }
    return Array.from(new Set(links))
}

function getDirectoryUrl(baseUrl: string): string {
    const parsed = new URL(baseUrl)
    parsed.pathname = parsed.pathname.replace(/[^/]+$/, '')
    parsed.search = ''
    parsed.hash = ''
    return parsed.toString()
}

function findArticleIds(block: string): string[] {
    const ids: string[] = []
    for (const match of block.matchAll(KFB_DETAIL_ID_RE)) {
        const id = match[1] || match[2] || match[3]
        if (id && Number(id) >= 100) ids.push(id)
    }
    return Array.from(new Set(ids))
}

function buildDetailUrl(directoryUrl: string, id: string): string {
    return new URL(`info_news_view.php?idx=${id}&${KFB_DETAIL_QUERY}`, directoryUrl).toString()
}

function buildDetailCandidates(block: string, listUrl: string): string[] {
    const directoryUrl = getDirectoryUrl(listUrl)
    return findArticleIds(block).map(id => buildDetailUrl(directoryUrl, id))
}

function buildListUrls(title: string): string[] {
    const searchTerm = title.trim()
    const urls: string[] = []
    for (const baseUrl of KFB_BASE_LIST_URLS) {
        urls.push(baseUrl)
        for (const page of [1, 2, 3]) {
            const pageUrl = new URL(baseUrl)
            pageUrl.searchParams.set('pg', String(page))
            urls.push(pageUrl.toString())
        }
        if (searchTerm) {
            const searchUrl = new URL(baseUrl)
            searchUrl.searchParams.set('col', 'subject')
            searchUrl.searchParams.set('sw', searchTerm)
            searchUrl.searchParams.set('pg', '1')
            urls.push(searchUrl.toString())
        }
    }
    return Array.from(new Set(urls))
}

function findMatchingBlock(html: string, targetTitle: string): string | null {
    for (const match of html.matchAll(ROW_RE)) {
        const block = match[0]
        if (normalizeTitle(block).includes(targetTitle)) {
            return block
        }
    }

    const normalizedHtml = normalizeTitle(html)
    const targetIndex = normalizedHtml.indexOf(targetTitle)
    if (targetIndex === -1) return null

    const roughIndex = Math.max(0, html.indexOf(targetTitle.slice(0, 6)))
    return html.slice(Math.max(0, roughIndex - 2000), roughIndex + 4000)
}

function isKfbDetailUrl(value: string): boolean {
    try {
        const parsed = new URL(value)
        return parsed.hostname.endsWith('kfb.or.kr') && parsed.pathname.endsWith('/info_news_view.php')
    } catch {
        return false
    }
}

async function findKfbOriginal(title: string): Promise<string | null> {
    const targetTitle = normalizeTitle(title)
    if (!targetTitle) return null

    for (const listUrl of buildListUrls(title)) {
        const html = await fetchHtml(listUrl)
        if (!html) continue

        const block = findMatchingBlock(html, targetTitle)
        if (!block) continue

        const links = findLinks(block, listUrl)
        const detailCandidates = [
            ...links.filter(isKfbDetailUrl),
            ...buildDetailCandidates(block, listUrl),
        ]
        for (const detailUrl of Array.from(new Set(detailCandidates))) {
            return detailUrl
        }
    }

    return null
}

export async function GET(request: NextRequest) {
    const title = request.nextUrl.searchParams.get('title') ?? ''
    const fallback = request.nextUrl.searchParams.get('fallback') || KFB_BASE_LIST_URLS[0]
    if (isKfbDetailUrl(fallback)) {
        return NextResponse.redirect(fallback)
    }

    const originalUrl = await findKfbOriginal(title)

    return NextResponse.redirect(originalUrl || fallback)
}
