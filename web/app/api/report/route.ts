
import { GoogleGenerativeAI } from '@google/generative-ai'
import { createClient } from '@supabase/supabase-js'
import { NextResponse } from 'next/server'

import { buildReportPrompt } from '@/lib/prompts/report'
import { ReportRequestSchema } from '@/lib/validation/report'

function getEnv() {
    return {
        supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL_V2,
        serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
        anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2,
        geminiApiKey: process.env.GEMINI_API_KEY,
        reportModel: process.env.GEMINI_REPORT_MODEL ?? 'gemini-3-flash-preview',
    }
}

export async function POST(req: Request) {
    const env = getEnv()

    if (!env.supabaseUrl) {
        return NextResponse.json({ error: 'Server Misconfiguration: SUPABASE_URL missing' }, { status: 500 })
    }
    if (!env.serviceRoleKey && !env.anonKey) {
        return NextResponse.json({ error: 'Server Misconfiguration: Supabase key missing' }, { status: 500 })
    }
    if (!env.geminiApiKey) {
        return NextResponse.json({ error: 'Server Misconfiguration: API Key missing' }, { status: 500 })
    }

    if (!env.serviceRoleKey && env.anonKey) {
        console.warn("[/api/report] using anon key fallback — RLS update policy is required for write operations")
    }

    // 1. Input validation — only articleId is accepted from the client.
    const raw = await req.json().catch(() => null)
    const parsed = ReportRequestSchema.safeParse(raw)
    if (!parsed.success) {
        return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
    }
    const { articleId } = parsed.data

    // 2. Server-side DB lookup — title/content/agency come exclusively from the row.
    const key = env.serviceRoleKey || env.anonKey
    const supabase = createClient(env.supabaseUrl, key as string)

    const { data: row, error: fetchError } = await supabase
        .from('articles')
        .select('id, title, content, agency, analysis_result')
        .eq('id', articleId)
        .single()

    if (fetchError || !row) {
        return NextResponse.json({ error: 'Article not found' }, { status: 404 })
    }

    const existingAnalysis = row.analysis_result || {}

    // 3. Cache hit
    if (existingAnalysis.detailed_report) {
        return NextResponse.json({ report: existingAnalysis.detailed_report })
    }

    // 4. Cache miss → Gemini
    const genAI = new GoogleGenerativeAI(env.geminiApiKey)
    const model = genAI.getGenerativeModel({ model: env.reportModel })
    const prompt = buildReportPrompt({
        agency: row.agency,
        title: row.title,
        content: row.content ?? '',
    })
    const result = await model.generateContent(prompt)
    const reportMarkdown = result.response.text()

    // 5. Persist
    const updatedAnalysis = {
        ...existingAnalysis,
        detailed_report: reportMarkdown,
        report_generated_at: new Date().toISOString(),
    }
    const { error: updateError } = await supabase
        .from('articles')
        .update({ analysis_result: updatedAnalysis })
        .eq('id', articleId)

    if (updateError) {
        return NextResponse.json({ error: 'Failed to persist report' }, { status: 500 })
    }

    return NextResponse.json({ report: reportMarkdown })
}
