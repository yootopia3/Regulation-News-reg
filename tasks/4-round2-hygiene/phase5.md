# Phase 5: api-report-integrity

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/refactor-round1.md` (§2 "분석 결과 JSON 키" 목록 — 이 phase는 이 키 셋을 건드리지 않는다)
- `CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. **source-first — 특히 `/api/report`의 라인 하나하나를 이해한 뒤 수정에 착수하라.**

- `web/app/api/report/route.ts` (이 phase의 주 수정 대상)
- `web/middleware.ts` (세션 경계 — 수정 금지)
- `web/lib/auth.ts` (존재하면)
- `web/tsconfig.json` (alias 확인)
- `web/package.json` (zod 추가 위치)

**호출부 식별**: 다음 grep으로 `/api/report`를 호출하는 모든 프런트 코드를 찾아라. 경로는 미리 박아두지 않았으니 이 phase에서 직접 식별하라:

```bash
grep -rn "/api/report" web/app web/components web/lib 2>/dev/null
```

이전 phase 산출물:

- Phase 4: `web/__tests__/api/report.test.ts` (cache hit/miss 2개 테스트 — 이 phase에서 확장)
- Phase 4: `web/vitest.config.ts`, `package.json` scripts

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **`/api/report`의 입력 무결성 수정 + 프롬프트 파일 분리 + 호출부 수정 + 주입 차단 테스트 red→green**를 다룬다. 병행 엔드포인트 없이 단일 PR로 교체한다 (결정 #8).

### 1. `zod` 의존성 추가

`web/package.json`의 `dependencies`에 `"zod": "^3.23.0"` 추가. 기존 의존성 수정·제거 금지.

### 2. `web/lib/validation/report.ts` 신규

```ts
import { z } from 'zod'

export const ReportRequestSchema = z.object({
  articleId: z.string().min(1),
})

export type ReportRequest = z.infer<typeof ReportRequestSchema>
```

**요청 body에서는 `articleId`만 수락.** `title`, `content`, `agency`가 전달되어도 **무시**한다 (zod는 unknown key를 기본 drop). strict mode로 400을 내고 싶지만, 기존 클라이언트가 보내고 있을 수 있으므로 drop-only가 안전하다.

### 3. `web/lib/prompts/report.ts` 신규

`web/app/api/report/route.ts:67-87`의 **현재 프롬프트 본문을 바이트 단위 동일하게** 이동한다. 문장 변경, 공백·들여쓰기 변경 금지.

```ts
export type ReportPromptInput = {
  agency: string
  title: string
  content: string
}

export function buildReportPrompt({ agency, title, content }: ReportPromptInput): string {
  return `
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
}
```

**위 프롬프트 문자열을 `web/app/api/report/route.ts`의 원본과 비교하여 한 문자라도 다르면 원본 쪽을 신뢰하라.** 반드시 먼저 원본을 읽고 그대로 옮겨라.

### 4. `web/app/api/report/route.ts` 재설계

**body에서 받는 것**: `articleId`만.

**서버가 DB에서 조회**: `articles` 테이블에서 `id, title, content, agency, analysis_result`를 한 번에 select.

핵심 구조 (시그니처·흐름만 — 세부 구현은 에이전트 재량):

```ts
import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { GoogleGenerativeAI } from '@google/generative-ai'
import { ReportRequestSchema } from '@/lib/validation/report'
import { buildReportPrompt } from '@/lib/prompts/report'

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
  if (!env.supabaseUrl) return NextResponse.json({ error: 'Server Misconfiguration: SUPABASE_URL missing' }, { status: 500 })
  if (!env.serviceRoleKey && !env.anonKey) return NextResponse.json({ error: 'Server Misconfiguration: Supabase key missing' }, { status: 500 })
  if (!env.geminiApiKey) return NextResponse.json({ error: 'Server Misconfiguration: API Key missing' }, { status: 500 })

  // 1. Input validation — 오직 articleId만
  const raw = await req.json().catch(() => null)
  const parsed = ReportRequestSchema.safeParse(raw)
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
  const { articleId } = parsed.data

  // 2. Server-side DB lookup — title/content/agency는 여기서만
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
```

**규칙:**
- `title`, `content`, `agency`는 **반드시 `row`에서 가져온다**. body에서 읽지 마라.
- `updateError` 발생 시 500 반환. silent swallow 금지.
- `articleId` 미존재 시 404.
- `body` parse 실패·schema 실패 시 400.
- 모델 ID는 `process.env.GEMINI_REPORT_MODEL ?? 'gemini-3-flash-preview'`. Phase 7이 env 단일화를 마무리한다.

### 5. 호출부 수정

`grep -rn "/api/report" web/app web/components web/lib`로 호출부를 모두 찾고, 각 호출의 body를 `{ articleId }`로 축소하라. 기존에 `title/content/agency`를 보내는 코드는 제거.

```ts
// before
fetch('/api/report', {
  method: 'POST',
  body: JSON.stringify({ articleId, title, content, agency }),
})

// after
fetch('/api/report', {
  method: 'POST',
  body: JSON.stringify({ articleId }),
})
```

호출부 수정이 타입 에러를 일으키면 해당 파일의 타입을 함께 좁혀라 (UI 로직 변경 금지).

### 6. 테스트 확장

`web/__tests__/api/report.test.ts`를 확장한다.

**Phase 4의 기존 테스트** (cache hit / cache miss)를 **새 body schema에 맞게 조정**하라. body는 `{ articleId }`만, Gemini mock에 전달되는 prompt의 content는 **mock Supabase가 반환한 row.content**여야 한다.

**신규 추가할 테스트 (Phase 5의 red→green 핵심)**:

1. **입력 무결성**: body에 `articleId` + `content: '악성 페이로드'`를 보내도, Gemini mock에 전달된 prompt 내부에 `'악성 페이로드'` 문자열이 **포함되지 않아야 한다**. prompt에는 mock Supabase가 반환한 row.content가 들어가야 한다.
2. **존재하지 않는 articleId**: supabase.single()이 `{ data: null, error: ... }`를 반환할 때 응답 status가 `404`.
3. **body parse 실패**: invalid JSON 또는 `articleId` 누락 시 status `400`.
4. **update 실패**: supabase.update가 error를 반환할 때 status `500`.

모든 신규 테스트는 이 phase 시작 시점에 **red**여야 한다 (현재 route.ts를 고치기 전). route.ts 수정 후 전체 green.

## Acceptance Criteria

```bash
# zod 설치
grep -q '"zod"' web/package.json
# 신규 파일
test -f web/lib/validation/report.ts
test -f web/lib/prompts/report.ts
# route.ts에 프롬프트 리터럴 제거 (buildReportPrompt import만)
! grep -q '당신은 한국 주요 시중은행' web/app/api/report/route.ts
grep -q 'buildReportPrompt' web/app/api/report/route.ts
grep -q 'ReportRequestSchema' web/app/api/report/route.ts

# --- Primary: vitest 주입 차단 테스트 green이 실제 입력 무결성을 보증한다 ---
cd web && npm install && npm test
cd web && npm run build
cd -

# --- Secondary: /api/report 호출부 파일을 식별하고, 각 파일 내에서
#     /api/report fetch 블록 주변(multi-line 포함)에 "content"/"title"/"agency"
#     JSON 키 리터럴이 남아있지 않은지 파일 단위로 확인 ---
python3 - <<'PY'
import re, subprocess, sys, pathlib
r = subprocess.run(
    ["grep", "-rlE", "/api/report", "web/app", "web/components", "web/lib"],
    capture_output=True, text=True,
)
files = [f for f in r.stdout.strip().splitlines() if f and "__tests__" not in f]
bad = []
key_re = re.compile(r"""["'](content|title|agency)["']\s*:""")
for p in files:
    try:
        src = pathlib.Path(p).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    # /api/report 등장 위치마다 앞뒤 windowed 스캔 (multi-line fetch body 커버)
    for m in re.finditer(r"/api/report", src):
        window = src[max(0, m.start() - 80): m.start() + 600]
        if key_re.search(window):
            bad.append(p)
            break
if bad:
    print("FAIL: these files still pass content/title/agency near /api/report:")
    for b in bad:
        print("  -", b)
    sys.exit(1)
print("OK: no caller file passes content/title/agency to /api/report")
PY

# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 5 status를 `"completed"`로 변경.

테스트가 실패하면 먼저 mock 설정을 점검하고, 그 다음 route.ts 로직을 점검하라. 프롬프트 문자열 하나라도 바이트가 다르면 AC가 실패할 수 있다. 원본 route.ts와 `web/lib/prompts/report.ts`의 프롬프트를 diff로 직접 비교하라.

3회 이상 실패 시 `"error"` + `error_message`. 사용자 개입 필요 시 `"blocked"`.

## 주의사항

- **프롬프트 문장 변경 금지.** 위치만 이동. 공백·들여쓰기·이모지·마크다운 헤더까지 그대로.
- **`web/middleware.ts` 수정 금지.** 세션 경계는 불변.
- **`web/components/` UI 로직 수정 금지.** `/api/report` 호출 body 축소만 허용.
- **분석 결과 JSON 키 셋 변경 금지.** `analysis_result.detailed_report`, `report_generated_at` 키 이름 그대로.
- **병행 엔드포인트 만들지 마라.** `/api/report`를 직접 교체한다 (결정 #8).
- **모델 ID 문자열 `'gemini-3-flash-preview'`를 route.ts의 fallback 외에는 넣지 마라.** Phase 7이 env 단일화를 마무리한다. 여기서는 `process.env.GEMINI_REPORT_MODEL ?? 'gemini-3-flash-preview'`까지만.
- **`updateError` silent swallow 복원 금지.** 기존 구현의 나쁜 동작이었다. 500 반환으로 수정.
- **`fetchError`를 console.error만 찍고 계속 진행하는 기존 동작 복원 금지.** 404로 끊는다.
- **zod strict 모드로 바꾸지 마라** (기존 클라이언트가 extra field를 보내고 있을 수 있으므로 drop-only).
- **`web/app/api/report/route.ts` 외의 API route 수정 금지.**
- **`src/`, `config/`, `.github/workflows/` 수정 금지.**
- 기존 pytest 테스트(Phase 3)를 깨지 마라.
