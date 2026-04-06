
import { GoogleGenerativeAI } from '@google/generative-ai'
import { createClient } from '@supabase/supabase-js'
import { NextResponse } from 'next/server'

// Initialize Supabase (V2 - Production Database)
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL_V2!
// Use Service Role Key for server-side updates (bypasses RLS)
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2!
const supabase = createClient(supabaseUrl, supabaseKey)

// Initialize Gemini
const apiKey = process.env.GEMINI_API_KEY
if (!apiKey) {
    console.error("❌ GEMINI_API_KEY is missing in environment variables!")
}
const genAI = new GoogleGenerativeAI(apiKey || '')

export async function POST(req: Request) {
    try {
        if (!apiKey) {
            return NextResponse.json({ error: 'Server Misconfiguration: API Key missing' }, { status: 500 })
        }

        const { articleId, title, content, agency } = await req.json()

        if (!articleId) {
            return NextResponse.json({ error: 'Article ID required' }, { status: 400 })
        }

        // 1. Check if report already exists in DB
        const { data: existingData, error: fetchError } = await supabase
            .from('articles')
            .select('analysis_result')
            .eq('id', articleId)
            .single()

        if (fetchError) {
            console.error("DB Fetch Error:", fetchError)
        }

        const existingAnalysis = existingData?.analysis_result || {}

        // If report exists, return it immediately
        if (existingAnalysis.detailed_report) {
            console.log("Returning cached report for", articleId)
            return NextResponse.json({ report: existingAnalysis.detailed_report })
        }

        // 2. Generate Report with Gemini
        console.log("Generating new report for", articleId)
        // Using "gemini-3-flash-preview" as requested for high-quality report generation
        const model = genAI.getGenerativeModel({ model: "gemini-3-flash-preview" })

        const prompt = `
        당신은 한국 주요 시중은행의 수석 분석 실무자입니다. 임원진에게 보고하는 레포트를 정확한 사실에 근거하여 명확하게 작성해야합니다. 주어진 규제/금융 관련 보도자료 또는 기사를 분석하여 경영진을 위한 심층 리포트를 작성하십시오.

        # **분석 원칙**
        1. **냉철하고 분석적인 분석**: 사실과 글의 내용에 기반하여 분석
        2. **엄격한 개조식**: 모든 문장은 명사형으로 종결 (예: '예상' O, '예상됨' X). **마침표(.) 사용 금지**
        3. **불확실성 배제**: 확실한 근거가 있는 내용만 포함하며, 추측성 내용은 제외
        4. **포괄적 정리**: **원문 내용이 길더라도, 중요 세부 사항을 생략하지 말고 빠짐없이 상세히 정리**

        # **리포트 구조 (Strict Structure)**
        1. **헤더**: 마크다운 헤더(#, ##)를 사용하여 계층 구조를 명확히 할 것
        2. **섹션 1**: 반드시 "1. 배경" 또는 "1. 목적" 중 적절한 것으로 시작할 것 (고정)
        3. **섹션 2~**: 이후 섹션은 자료 내용을 분석하여 가장 적절한 **한글 소제목**을 스스로 결정하여 구성할 것 (자율)
        4. **제언/파급효과**: 내용이 확실한 경우에만 별도 섹션으로 포함하고, 불확실하면 제외할 것

        # **입력 자료**
        - Agency: ${agency}
        - Title: ${title}
        - Content:
        ${content.substring(0, 8000)}
        `

        const result = await model.generateContent(prompt)
        const response = await result.response
        const reportMarkdown = response.text()

        // 3. Save to DB (Merge with existing analysis_result)
        const updatedAnalysis = {
            ...existingAnalysis,
            detailed_report: reportMarkdown,
            report_generated_at: new Date().toISOString()
        }

        const { error: updateError } = await supabase
            .from('articles')
            .update({ analysis_result: updatedAnalysis })
            .eq('id', articleId)

        if (updateError) {
            console.error("Failed to save report:", updateError)
            // We still return the generated report even if save failed
        }

        return NextResponse.json({ report: reportMarkdown })

    } catch (error) {
        console.error("API Error:", error)
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 })
    }
}
