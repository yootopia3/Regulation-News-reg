# Phase 4: web-test-harness

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/refactor-round1.md` (분석 결과 JSON 키 규약 — §2 말미)
- `CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. **source-first — 특히 `/api/report` 핸들러의 현재 분기 구조를 손가락으로 짚어 이해한 뒤에 테스트를 써라.**

- `web/package.json`
- `web/next.config.ts`
- `web/tsconfig.json`
- `web/middleware.ts` (세션 경계 확인, 이 phase에서 수정 금지)
- `web/app/api/report/route.ts` (이 phase의 **회귀 그물 대상**, **수정 금지**)
- `web/lib/` 내 유틸 (존재하면)

이전 phase 산출물:

- Phase 1: `.env.example`, `web/.env.local.example`
- Phase 2: `.github/workflows/ci.yml` (gitleaks job)
- Phase 3: `requirements-dev.txt`, `tests/unit/**`, `ci.yml`에 python-test job 추가됨

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **Vitest 셋업 + `/api/report`의 안정 동작(cache hit/miss)에 대한 회귀 테스트 + CI web job 추가**만 다룬다. Phase 5에서 입력 무결성 테스트를 red로 추가하기 위한 그물망이다.

### 1. Vitest 의존성 추가

`web/package.json`의 `devDependencies`에 다음 추가:

```json
"vitest": "^1.6.0",
"@vitest/ui": "^1.6.0",
"@types/node": "^20"
```

`scripts`에 다음 추가 (기존 scripts는 유지):

```json
"test": "vitest run",
"test:watch": "vitest"
```

**기존 의존성·스크립트 삭제·수정 금지.**

### 2. `web/vitest.config.ts` 신규

```ts
import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  test: {
    environment: 'node',
    globals: false,
    include: ['__tests__/**/*.test.ts'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
})
```

`@` alias는 `web/tsconfig.json`의 paths와 동일해야 한다. tsconfig에 `@/*` alias가 없다면 이 alias도 쓰지 말고 상대경로 import로 가라.

### 3. `web/__tests__/api/report.test.ts` 신규

**이 테스트는 `/api/report`의 안정 동작만 박제한다.** 현재 구현의 나쁜 동작(DB fetch 에러 시 silent continue 등)은 **박제하지 마라**. 오직 다음 두 안정 시나리오만 검증:

1. **캐시 히트**: 해당 `articleId`의 `analysis_result.detailed_report`가 이미 존재할 때, Gemini 호출 없이 캐시된 값을 반환한다.
2. **캐시 미스**: `detailed_report`가 없을 때, Gemini mock이 호출되고 생성된 텍스트가 응답으로 돌아오며 Supabase `update`가 호출된다.

구조:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@supabase/supabase-js', () => {
  // fluent chain mock
  const mkSupabase = (overrides: any = {}) => ({
    from: vi.fn().mockReturnThis(),
    select: vi.fn().mockReturnThis(),
    eq: vi.fn().mockReturnThis(),
    single: vi.fn().mockResolvedValue(overrides.single ?? { data: null, error: null }),
    update: vi.fn().mockReturnThis(),
  })
  return {
    createClient: vi.fn(),
    __mkSupabase: mkSupabase,
  }
})

vi.mock('@google/generative-ai', () => ({
  GoogleGenerativeAI: vi.fn().mockImplementation(() => ({
    getGenerativeModel: vi.fn().mockReturnValue({
      generateContent: vi.fn().mockResolvedValue({
        response: { text: () => 'GENERATED_REPORT_MARKDOWN' },
      }),
    }),
  })),
}))

// env stub for getEnv()
beforeEach(() => {
  process.env.NEXT_PUBLIC_SUPABASE_URL_V2 = 'https://test.supabase.co'
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'test-service-key'
  process.env.GEMINI_API_KEY = 'test-gemini-key'
})

describe('/api/report', () => {
  it('returns cached report when detailed_report exists', async () => {
    // arrange: supabase.single() returns analysis_result with detailed_report
    // act: POST handler with { articleId, title, content, agency }
    //      (현재 구현이 body의 title/content/agency를 읽으므로 동일 포맷 전달)
    // assert: response.report === cached value,
    //         Gemini generateContent가 호출되지 않음
  })

  it('generates and stores a new report on cache miss', async () => {
    // arrange: supabase.single() returns empty analysis_result
    // act: POST handler
    // assert: Gemini mock이 1회 호출, supabase.update가 1회 호출,
    //         응답 report === 'GENERATED_REPORT_MARKDOWN'
  })
})
```

구현 세부(mock chain 조립 방법)는 vitest/supabase 문서를 보고 판단하되, **다음 시나리오는 이 phase에 쓰지 마라:**

- DB fetch 에러 시 동작 (현재 구현이 silent하게 이어가는 나쁜 동작 — 박제 금지)
- 입력 무결성 (body의 content 주입 차단) — Phase 5의 red→green 범위
- 404/400 응답 — Phase 5의 범위

### 4. `.github/workflows/ci.yml` 확장

Phase 2·3에서 만든 `ci.yml`에 `web-test` job을 추가한다. 기존 job 수정·삭제 금지.

```yaml
  web-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: web/package-lock.json
      - run: npm ci
      - run: npm test
      - run: npm run build
```

## Acceptance Criteria

```bash
# Vitest 의존성·스크립트
grep -q '"vitest"' web/package.json
grep -q '"test": "vitest run"' web/package.json
# 설정 파일
test -f web/vitest.config.ts
test -f web/__tests__/api/report.test.ts
# 테스트 실행 (cache hit/miss 2개)
cd web && npm install && npm test
# 빌드 무회귀
cd web && npm run build
cd -
# CI yml 확장 확인
grep -q 'web-test:' .github/workflows/ci.yml
grep -q 'npm test' .github/workflows/ci.yml
# Phase 2/3 job 유지 확인
grep -q 'gitleaks:' .github/workflows/ci.yml
grep -q 'python-test:' .github/workflows/ci.yml
# web 핸들러 수정 없음
git diff --quiet HEAD -- web/app/api/report/route.ts
# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 4 status를 `"completed"`로 변경.

`npm install` 시 네트워크 이슈가 있다면 `npm ci`로 재시도. 3회 이상 실패 시 `"error"` + `error_message`. 사용자 개입 필요 시 `"blocked"`.

## 주의사항

- **`web/app/api/report/route.ts` 수정 금지.** 이 phase는 회귀 그물망만 치고, 실제 재설계는 Phase 5다. `git diff --quiet`가 통과해야 한다.
- **`web/middleware.ts`, `web/lib/auth.ts` 수정 금지.** 세션 경계는 Round 2 내내 불변.
- **`web/components/` 수정 금지.**
- **DB fetch 에러 시 silent continue 동작은 박제하지 마라.** 현재 구현의 나쁜 동작이고 Phase 5에서 고친다. 이 phase의 테스트에 그 경로를 포함시키면 Phase 5가 기존 테스트를 깨면서 진행해야 해서 의미가 없다.
- **입력 무결성 테스트(body content 주입 차단)를 이 phase에 쓰지 마라.** Phase 5의 red→green 범위다.
- **pipeline/통합 테스트 금지.** 이 phase는 `/api/report` 단위 테스트 2개로 한정한다.
- **Jest로 전환하지 마라.** Vitest로 결정됨.
- **`ci.yml`에서 기존 `gitleaks`, `python-test` job 삭제·수정 금지.** append만.
- **`package.json`의 기존 의존성/스크립트 삭제·다운그레이드 금지.** 추가만.
- 기존 테스트를 깨뜨리지 마라 (현 시점 `web/`에 테스트가 없으면 N/A).
