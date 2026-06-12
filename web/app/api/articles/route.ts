import { createClient } from '@supabase/supabase-js'
import { NextResponse } from 'next/server'

import { pressAgencies, regulationAgencies, sanctionAgencies } from '@/components/dashboard/constants'

const ARTICLE_COLUMNS =
    'id,title,agency,category,published_at,published_at_source,created_at,link,source_org,source_name,subcategory,analysis_result,view_count,star_rating'

const ARTICLE_CATEGORY = {
    press: 'press_release',
    regulation: 'regulation_notice',
    sanction: 'sanction_notice',
} as const

type RawArticleRow = Record<string, unknown>
type ArticleQueryResult = { data: unknown[] | null; error: unknown }

type SafeAnalysisResult = {
    summary?: string[]
    importance_score?: number
    risk_level?: string
    keywords?: string[]
    pdf_url?: string
}

type SafeArticle = {
    id: string
    title: string
    agency: string
    category?: string | null
    published_at: string
    published_at_source?: string | null
    created_at?: string | null
    link: string
    source_org?: string | null
    source_name?: string | null
    subcategory?: string | null
    analysis_result: SafeAnalysisResult | null
    view_count?: number | null
    star_rating?: number | null
}

function normalizeSupabaseUrl(value: string | undefined): string | undefined {
    const trimmed = value?.trim()
    if (!trimmed) return undefined

    try {
        const parsed = new URL(trimmed)
        if (parsed.hostname.endsWith('.supabase.co')) {
            return parsed.origin
        }
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

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
    return Array.isArray(value) && value.every(item => typeof item === 'string')
}

function sanitizeAnalysisResult(value: unknown): SafeAnalysisResult | null {
    if (!isRecord(value)) return null

    const result: SafeAnalysisResult = {}
    if (isStringArray(value.summary)) result.summary = value.summary
    if (typeof value.importance_score === 'number') result.importance_score = value.importance_score
    if (typeof value.risk_level === 'string') result.risk_level = value.risk_level
    if (isStringArray(value.keywords)) result.keywords = value.keywords
    if (typeof value.pdf_url === 'string') result.pdf_url = value.pdf_url

    return Object.keys(result).length > 0 ? result : null
}

function sanitizeArticle(row: RawArticleRow): SafeArticle | null {
    const { id, title, agency, published_at: publishedAt, link } = row
    if (
        typeof id !== 'string' ||
        typeof title !== 'string' ||
        typeof agency !== 'string' ||
        typeof publishedAt !== 'string' ||
        typeof link !== 'string'
    ) {
        return null
    }

    const article: SafeArticle = {
        id,
        title,
        agency,
        published_at: publishedAt,
        link,
        analysis_result: sanitizeAnalysisResult(row.analysis_result),
    }

    for (const key of ['category', 'published_at_source', 'created_at', 'source_org', 'source_name', 'subcategory'] as const) {
        if (typeof row[key] === 'string' || row[key] === null) {
            article[key] = row[key]
        }
    }
    for (const key of ['view_count', 'star_rating'] as const) {
        if (typeof row[key] === 'number' || row[key] === null) {
            article[key] = row[key]
        }
    }

    return article
}

export async function GET() {
    const env = getEnv()
    if (!env.supabaseUrl) {
        return NextResponse.json({ error: 'Server Misconfiguration: Supabase URL missing' }, { status: 500 })
    }
    if (!env.supabaseKey) {
        return NextResponse.json({ error: 'Server Misconfiguration: Supabase key missing' }, { status: 500 })
    }

    let results: ArticleQueryResult[]
    try {
        const supabase = createClient(env.supabaseUrl, env.supabaseKey)
        results = await Promise.all([
            supabase
                .from('articles')
                .select(ARTICLE_COLUMNS)
                .in('agency', pressAgencies)
                .or(`category.eq.${ARTICLE_CATEGORY.press},category.is.null`)
                .order('published_at', { ascending: false })
                .limit(1000),
            supabase
                .from('articles')
                .select(ARTICLE_COLUMNS)
                .in('agency', regulationAgencies)
                .eq('category', ARTICLE_CATEGORY.regulation)
                .order('published_at', { ascending: false })
                .limit(1000),
            supabase
                .from('articles')
                .select(ARTICLE_COLUMNS)
                .in('agency', sanctionAgencies)
                .eq('category', ARTICLE_CATEGORY.sanction)
                .order('published_at', { ascending: false })
                .limit(1000),
        ])
    } catch (error) {
        console.error('Error fetching articles:', error)
        return NextResponse.json({ error: 'Failed to fetch articles' }, { status: 500 })
    }

    const errors = results.map(result => result.error).filter(Boolean)
    if (errors.length > 0) {
        console.error('Error fetching articles:', errors)
        return NextResponse.json({ error: 'Failed to fetch articles' }, { status: 500 })
    }

    const articles = results
        .flatMap(result => (result.data ?? []) as RawArticleRow[])
        .map(sanitizeArticle)
        .filter((article): article is SafeArticle => article !== null)
    const dedupedArticles = Array.from(new Map(articles.map(article => [article.id, article])).values())
        .sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime())

    return NextResponse.json({ articles: dedupedArticles })
}
