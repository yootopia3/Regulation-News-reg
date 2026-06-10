import { createClient } from '@supabase/supabase-js'
import { NextResponse } from 'next/server'

type ArticleRow = {
    title: string
    agency: string
    category: string | null
    published_at: string
    link: string
    analysis_result: {
        summary?: string[]
        importance_score?: number
    } | null
}

const AGENCY_NAMES: Record<string, string> = {
    MOEF: '기획재정부',
    FSC: '금융위원회',
    FSS: '금융감독원',
    BOK: '한국은행',
    MAFRA: '농식품부',
    FSC_REG: '금융위원회',
    FSS_REG: '금융감독원',
    FSS_REG_INFO: '금융감독원',
    FSS_SANCTION: '금감원 제재',
    FSS_MGMT_NOTICE: '경영유의사항',
}

const CATEGORY_NAMES: Record<string, string> = {
    press_release: '보도자료',
    regulation_notice: '규제개정',
    sanction_notice: '제재 공시',
}

function normalizeSupabaseUrl(value: string | undefined): string | undefined {
    const trimmed = value?.trim()
    if (!trimmed) return undefined

    try {
        const parsed = new URL(trimmed)
        if (parsed.hostname.endsWith('.supabase.co')) return parsed.origin
    } catch {
        return trimmed
    }

    return trimmed
}

function getEnv() {
    const useV2 = process.env.NEXT_PUBLIC_USE_V2_DB === 'true'
    const rawSupabaseUrl = useV2
        ? process.env.NEXT_PUBLIC_SUPABASE_URL_V2
        : process.env.NEXT_PUBLIC_SUPABASE_URL
    const anonKey = useV2
        ? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2
        : process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

    return {
        supabaseUrl: normalizeSupabaseUrl(rawSupabaseUrl),
        supabaseKey: process.env.SUPABASE_SERVICE_ROLE_KEY || anonKey,
    }
}

function escapeHtml(value: string): string {
    return value
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;')
}

function getKstDateParts(date = new Date()) {
    const formatter = new Intl.DateTimeFormat('ko-KR', {
        timeZone: 'Asia/Seoul',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        weekday: 'short',
    })
    const parts = Object.fromEntries(formatter.formatToParts(date).map(part => [part.type, part.value]))
    return {
        year: parts.year,
        month: parts.month,
        day: parts.day,
        weekday: parts.weekday,
    }
}

function getKstDayRange() {
    const now = new Date()
    const kstNow = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Seoul' }))
    const startKst = new Date(kstNow)
    startKst.setHours(0, 0, 0, 0)
    const endKst = new Date(startKst)
    endKst.setDate(endKst.getDate() + 1)

    return {
        startUtc: new Date(startKst.getTime() - 9 * 60 * 60 * 1000).toISOString(),
        endUtc: new Date(endKst.getTime() - 9 * 60 * 60 * 1000).toISOString(),
    }
}

function getSummary(article: ArticleRow): string {
    const summary = article.analysis_result?.summary
    if (Array.isArray(summary) && summary.length > 0) return summary.join(' ')
    return '세부 요약은 원문 확인이 필요합니다.'
}

function buildReportHtml(articles: ArticleRow[]): string {
    const date = getKstDateParts()
    const highPriority = articles.filter(article => {
        const score = article.analysis_result?.importance_score ?? 3
        return score >= 4 || article.category === 'sanction_notice'
    })
    const categoryCounts = articles.reduce<Record<string, number>>((acc, article) => {
        const category = article.category || 'press_release'
        acc[category] = (acc[category] || 0) + 1
        return acc
    }, {})

    const rows = articles.map((article, index) => {
        const category = article.category || 'press_release'
        const score = article.analysis_result?.importance_score ?? '-'
        return `
            <tr>
                <td class="center">${index + 1}</td>
                <td>
                    <div class="article-title">${escapeHtml(article.title)}</div>
                    <div class="summary">${escapeHtml(getSummary(article))}</div>
                    <div class="source">${escapeHtml(article.link)}</div>
                </td>
                <td>${escapeHtml(AGENCY_NAMES[article.agency] || article.agency)}</td>
                <td>${escapeHtml(CATEGORY_NAMES[category] || category)}</td>
                <td class="center">${escapeHtml(String(score))}</td>
            </tr>
        `
    }).join('')

    const highlightItems = highPriority.slice(0, 5).map(article => `
        <li>
            <strong>${escapeHtml(article.title)}</strong>
            <span>${escapeHtml(AGENCY_NAMES[article.agency] || article.agency)} · ${escapeHtml(getSummary(article))}</span>
        </li>
    `).join('')

    return `<!doctype html>
<html>
<head>
    <meta charset="utf-8" />
    <title>아침에 읽는 규제변화</title>
    <style>
        body { font-family: "Malgun Gothic", Arial, sans-serif; color: #1a1a1a; line-height: 1.55; }
        .page { width: 720px; margin: 0 auto; }
        .header { border-bottom: 4px solid #005bac; padding-bottom: 14px; margin-bottom: 18px; }
        .date { color: #666; font-size: 14px; }
        h1 { color: #005bac; font-size: 30px; margin: 6px 0 4px; }
        .subtitle { color: #444; font-size: 13px; }
        .cards { display: table; width: 100%; margin: 18px 0; table-layout: fixed; }
        .card { display: table-cell; padding: 13px; color: white; text-align: center; font-weight: bold; }
        .card.blue { background: #0d5cab; }
        .card.sky { background: #1e88bc; }
        .card.red { background: #c0392b; }
        .card .num { display: block; font-size: 26px; margin-top: 4px; }
        .section-title { background: #d0e4f5; color: #0d2f8b; padding: 10px 12px; font-weight: bold; margin-top: 18px; }
        .brief { background: #f7fbff; border-left: 5px solid #005bac; padding: 12px 14px; }
        li { margin-bottom: 9px; }
        li span { display: block; color: #555; margin-top: 2px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th { background: #0d2f8b; color: white; padding: 8px; border: 1px solid #cfcfcf; }
        td { padding: 8px; border: 1px solid #cfcfcf; vertical-align: top; }
        .center { text-align: center; }
        .article-title { font-weight: bold; color: #111; }
        .summary { color: #555; margin-top: 4px; }
        .source { color: #777; font-size: 10px; margin-top: 6px; word-break: break-all; }
        .footer { margin-top: 18px; color: #777; font-size: 11px; }
    </style>
</head>
<body>
    <div class="page">
        <div class="header">
            <div class="date">${date.year}. ${date.month}. ${date.day}. (${date.weekday})</div>
            <h1>아침에 읽는 규제변화</h1>
            <div class="subtitle">IBK 내부통제총괄부 · 자동 생성 규제 모니터링 리포트</div>
        </div>
        <div class="cards">
            <div class="card blue">전체 기사<span class="num">${articles.length}</span></div>
            <div class="card sky">규제개정<span class="num">${categoryCounts.regulation_notice || 0}</span></div>
            <div class="card red">중점 확인<span class="num">${highPriority.length}</span></div>
        </div>
        <div class="section-title">오늘의 요약</div>
        <div class="brief">오늘 수집된 규제·보도·제재 공시 중 내부통제 관점에서 확인할 수 있는 항목을 정리했습니다.</div>
        <div class="section-title">중점 확인 항목</div>
        ${highlightItems ? `<ul>${highlightItems}</ul>` : '<p>오늘 중점 확인 항목은 없습니다.</p>'}
        <div class="section-title">오늘의 규제 브리프</div>
        <table>
            <thead><tr><th style="width:45px;">No</th><th>내용</th><th style="width:95px;">기관</th><th style="width:90px;">구분</th><th style="width:60px;">중요도</th></tr></thead>
            <tbody>${rows || '<tr><td colspan="5" class="center">오늘 생성할 기사 데이터가 없습니다.</td></tr>'}</tbody>
        </table>
        <div class="footer">본 문서는 Supabase articles 데이터를 기준으로 자동 생성되었습니다. 세부 판단 및 조치 여부는 원문과 담당부서 검토가 필요합니다.</div>
    </div>
</body>
</html>`
}

export async function GET() {
    const env = getEnv()
    if (!env.supabaseUrl || !env.supabaseKey) {
        return NextResponse.json({ error: 'Supabase is not configured' }, { status: 500 })
    }

    const { startUtc, endUtc } = getKstDayRange()
    const supabase = createClient(env.supabaseUrl, env.supabaseKey)
    const { data, error } = await supabase
        .from('articles')
        .select('title,agency,category,published_at,link,analysis_result')
        .gte('published_at', startUtc)
        .lt('published_at', endUtc)
        .order('published_at', { ascending: false })
        .limit(200)

    if (error) {
        console.error('Failed to generate daily report:', error)
        return NextResponse.json({ error: 'Failed to generate daily report' }, { status: 500 })
    }

    const html = buildReportHtml((data ?? []) as ArticleRow[])
    const reportDate = getKstDateParts()
    const filename = `IBK_daily_regulatory_report_${reportDate.year}${reportDate.month}${reportDate.day}.doc`

    return new NextResponse(html, {
        headers: {
            'Content-Type': 'application/msword; charset=utf-8',
            'Content-Disposition': `attachment; filename="${filename}"`,
            'Cache-Control': 'no-store',
        },
    })
}
