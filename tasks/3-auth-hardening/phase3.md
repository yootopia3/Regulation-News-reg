# Phase 3: api-report-safety-net

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `CLAUDE.md` — phase 실행 규약.
- `tasks/3-auth-hardening/index.json` — task scope. 본 phase는 `/api/report` 의 misconfig 가시성만 보강한다. 구조 개편 금지.

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. **source-first** 다:

- `web/app/api/report/route.ts` — 현재 모듈 최상단(L7-10)에서 `process.env.NEXT_PUBLIC_SUPABASE_URL_V2!`, `process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2!` 를 읽고 `createClient(...)` 를 모듈 import 시점에 실행한다. env가 모두 미설정인 dev 환경에서 빌드/import가 깨질 수 있는 패턴이다.
- `web/components/ReportModal.tsx` — `/api/report` 의 라이브 caller. 본 phase의 변경이 이 caller의 요청 형식/응답 처리와 호환되어야 한다.
- `scripts/v2_schema_setup.sql` — L47-52 의 anon UPDATE 정책이 운영 흐름에서 anon fallback에 의존 중일 가능성의 근거. **본 phase에서 이 파일을 수정하지 마라.** 단지 운영 가정이 어떻게 형성됐는지 이해 목적.

이전 phase 산출물:

- `tasks/3-auth-hardening/phase1.md` 결과(백엔드 hygiene). 본 phase 빌드 검증의 전반부(`venv/bin/python -c ...`)가 phase 1 결과에 의존.
- `tasks/3-auth-hardening/phase2.md` 결과(프론트 인증). 본 phase가 손대는 `/api/report` 는 phase 2의 미들웨어로 이미 인증 가드 안에 들어가 있다. 즉 외부 무단 호출 표면은 phase 2가 닫았고, 본 phase는 misconfig 가시성만 보강한다.

문서보다 코드가 우선이다.

## 작업 내용

본 phase는 단일 파일 변경. 핵심 원칙: **fallback 자체는 유지**, **module-top side effect만 함수 안으로 옮긴다**, **misconfig 시 가시성만 추가**.

### 1. module-top side effect → 요청 시점으로 이동

`web/app/api/report/route.ts` 의 모듈 최상단(현재 L6-17 사이)에 위치한 다음 요소들을 POST 핸들러 안의 helper로 이동:

- `const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL_V2!` (현 L7)
- `const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2!` (현 L9)
- `const supabase = createClient(supabaseUrl, supabaseKey)` (현 L10)
- `const apiKey = process.env.GEMINI_API_KEY` (현 L13)
- `const genAI = new GoogleGenerativeAI(apiKey || '')` (현 L17)

이동 방식 (시그니처 수준):

```ts
function getEnv() {
  return {
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL_V2,
    serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
    anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2,
    geminiApiKey: process.env.GEMINI_API_KEY,
  };
}
```

POST 핸들러 진입 직후 `const env = getEnv();` 호출 후 createClient/GoogleGenerativeAI 인스턴스 생성. 모듈 최상단에서는 import 외 어떤 실행도 하지 마라.

### 2. 요청 시점 env 가드

POST 핸들러 진입 직후, body 파싱보다 먼저:

- `if (!env.supabaseUrl)` → `return NextResponse.json({ error: 'Server Misconfiguration: SUPABASE_URL missing' }, { status: 500 })`
- `if (!env.serviceRoleKey && !env.anonKey)` → `return NextResponse.json({ error: 'Server Misconfiguration: Supabase key missing' }, { status: 500 })`
- 기존 Gemini API key 가드(`if (!apiKey) return NextResponse.json({error: 'Server Misconfiguration: API Key missing'},{status:500})`)는 그대로 유지하되, 새 `env.geminiApiKey` 변수를 참조하도록 갱신.

### 3. anon fallback warning log

service-role 키가 없고 anon 키만 있을 때, 요청 시점에 1회 warning을 출력:

- `if (!env.serviceRoleKey && env.anonKey) console.warn("[/api/report] using anon key fallback — RLS update policy is required for write operations")`
- 호출 시점에 매번 출력해도 무방(1회 캐싱 불필요). vercel logs에서 패턴 추적 가능하면 충분.

### 4. createClient 키 선택은 그대로 유지

```ts
const key = env.serviceRoleKey || env.anonKey;
const supabase = createClient(env.supabaseUrl, key);
```

**fallback 자체는 절대 제거하지 마라.** service-role 강제 금지.

### 5. POST 핸들러의 나머지 로직(L19-103)은 그대로 유지

- body 파싱, articleId 검증, `existingData?.analysis_result` 캐시 조회, `getGenerativeModel(...)` 호출, prompt 본문, `analysis_result` merge update, 응답 형식 모두 동일.
- prompt 문자열(L55-75)은 한 글자도 건드리지 마라.

## Acceptance Criteria

```bash
# 1. 모듈 최상단에서 createClient/process.env 즉시 실행이 사라졌는지 (함수 안에만 존재해야 함)
test -z "$(awk '/^export async function POST/{exit} 1' web/app/api/report/route.ts | grep -E '(createClient|new GoogleGenerativeAI)\(')"

# 2. 요청 시점 가드 존재 (둘 다 미설정 시 500)
grep -q 'Supabase key missing' web/app/api/report/route.ts

# 3. anon fallback warning 존재
grep -q 'using anon key fallback' web/app/api/report/route.ts

# 4. fallback 유지 — service-role 또는 anon 키를 모두 참조함
grep -q 'SUPABASE_SERVICE_ROLE_KEY' web/app/api/report/route.ts
grep -q 'SUPABASE_ANON_KEY_V2' web/app/api/report/route.ts

# 5. prompt 본문이 변경되지 않음 (Gemini 프롬프트 첫 줄 키워드 보존)
grep -q '한국 주요 시중은행의 수석 분석 실무자' web/app/api/report/route.ts

# 6. 응답 스키마(`report` 키) 보존
grep -q "'report':\|\"report\":\|report: reportMarkdown\| report: " web/app/api/report/route.ts

# 7. SQL 파일과 RLS 관련 파일이 손대지지 않음
git diff --quiet scripts/v2_schema_setup.sql
git diff --quiet db/schema.sql

# 8. task 단위 build_command 통과
venv/bin/python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer" && cd web && npm run build
```

## AC 검증 방법

위 8개 커맨드를 직접 실행하라. 모두 통과하면 phase 3 status를 `"completed"` 로 변경.

수정 3회 이상 실패하면 `"error"` + `error_message` 기록.

다음은 즉시 `"blocked"`:

- `web/node_modules/` 가 존재하지 않거나 `next` 바이너리가 설치되지 않아 `cd web && npm run build` 가 환경 사유로 실패할 때(`next: not found`, `MODULE_NOT_FOUND` 등). 사용자가 사전에 `cd web && npm install` 을 1회 수동 수행해야 한다.
- `venv/` 가 존재하지 않거나 백엔드 dependencies(`pip install -r requirements.txt`)가 미설치되어 import smoke 가 환경 사유로 실패할 때.
- Next.js 16의 `NextResponse.json` API가 변경되어 본 phase의 가드 패턴이 동작하지 않을 때.
- `web/app/api/report/route.ts` 가 phase 2와 충돌해 빌드가 깨질 때(드물지만 가능).

## 주의사항

- **service-role 키를 강제로 요구하지 마라.** 운영이 anon UPDATE 정책에 의존 중일 가능성이 매우 크다(`scripts/v2_schema_setup.sql:47-52` 참조). fallback 제거 = 운영 깨짐.
- **RLS 정책을 변경하지 마라.** `scripts/v2_schema_setup.sql`, `db/schema.sql` 모두 본 phase에서 손대지 않는다.
- **env 변수 이름을 변경/추가/제거하지 마라.** `NEXT_PUBLIC_SUPABASE_URL_V2`, `NEXT_PUBLIC_SUPABASE_ANON_KEY_V2`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY` 그대로.
- **Gemini prompt 본문(L55-75)을 변경하지 마라.** 한 글자도.
- **응답 스키마를 변경하지 마라.** `{ report: reportMarkdown }` 형식 그대로.
- **`articles` 테이블 update 흐름(`existingAnalysis`, `updatedAnalysis`)을 변경하지 마라.** merge update 로직 그대로.
- 다른 `/api/*` route 본문 수정 금지.
- 새 npm dependency 추가 금지.
- 본 phase에서 백엔드(`src/`), DB(`db/`), `web/middleware.ts`, `web/lib/auth.ts`, `web/app/login/page.tsx`, 문서를 건드리지 마라.
