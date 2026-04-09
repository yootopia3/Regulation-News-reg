# Phase 6: dashboard-render-smoke-test

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C4 / P1-6c, §7.2, §8.2 phase 6, §9.2)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx` — phase 1–5 가 적용된 상태.
- `/home/pacer/projects/reg_brief/web/components/dashboard/Sidebar.tsx` (phase 4)
- `/home/pacer/projects/reg_brief/web/components/dashboard/AgencyIcon.tsx` (phase 2)
- `/home/pacer/projects/reg_brief/web/components/dashboard/useHasNewByCategory.ts` (phase 3)
- `/home/pacer/projects/reg_brief/web/components/dashboard/constants.ts` (phase 1)
- `/home/pacer/projects/reg_brief/web/utils/supabase/client.ts` — DashboardV2 가 default 가 아닌 named export `supabase` 를 import 하는 경로 확인.
- `/home/pacer/projects/reg_brief/web/utils/newArticleTracker.ts` — `getLastVisitTime`, `updateLastVisitTime`, `isArticleNew` 사용처.
- `/home/pacer/projects/reg_brief/web/__tests__/api/report.test.ts` — 기존 vitest mock 패턴 참고.
- `/home/pacer/projects/reg_brief/web/package.json` (현재 devDeps 확인: vitest 1.6.0 + @vitest/ui. `@testing-library/react`, `jsdom`, `@testing-library/jest-dom` 가 **없다**. phase 6 에서 추가 필요)
- `/home/pacer/projects/reg_brief/web/vitest.config.ts` — **이미 존재**. 현재 값:
  - `environment: 'node'`
  - `include: ['__tests__/**/*.test.ts']` (`.tsx` **미포함** — phase 6 에서 반드시 확장)
  - `globals: false` (이건 그대로 유지 가능 — 본 phase 의 테스트는 vitest API 를 명시 import 한다)

이전 phase의 작업물도 확인하라:

- 모든 phase 1–5 의 산출물.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: `DashboardV2` 가 일반적인 케이스에서 mount 되고, "검색 결과가 없습니다." empty state 를 노출하는지 vitest + jsdom 으로 smoke 검증.

1. **devDependency 보강**:
   - `web/package.json` 의 devDeps 에 다음 3 개를 추가 후 `npm install`:
     - `"@testing-library/react": "^16.1.0"` — **반드시 ^16.1.0 이상**. 16.0.x 는 React 19 의 `act` import 경로 변경으로 깨지는 것이 보고되어 있다. 16.1.0 부터 React 19 대응 패치가 들어 있다.
     - `"@testing-library/jest-dom": "^6.6.0"`
     - `"jsdom": "^25.0.0"`
   - **이미 있으면 추가 설치 금지**. 버전이 위 최소값보다 낮으면 minor upgrade 만 허용 (16.0.x → 16.1.x 같은 경우).
   - **vitest 자체는 업그레이드 금지**. 현재 `^1.6.0` 으로 고정되어 있고, 이를 2.x 로 올리는 것은 phase 6 의 scope 가 아니다. 만약 `@testing-library/react@16.1+` 가 vitest 1.6 과 호환 충돌을 일으킨다면 phase 6 status 를 즉시 `error` 로 마킹하고 `error_message` 에 호환 충돌 내용을 기록한 뒤 작업을 중단하라 — 사용자 결정 필요.

2. **vitest.config.ts 수정** (이미 존재. 부분 치환):
   - 기존 (현재 파일):
     ```typescript
     export default defineConfig({
       test: {
         environment: 'node',
         globals: false,
         include: ['__tests__/**/*.test.ts'],
       },
       resolve: { alias: { '@': path.resolve(__dirname, '.') } },
     })
     ```
   - 수정 후:
     ```typescript
     export default defineConfig({
       test: {
         environment: 'jsdom',                              // 'node' → 'jsdom'
         globals: false,                                    // 그대로 유지 (명시 import 사용)
         include: ['__tests__/**/*.test.{ts,tsx}'],         // .test.tsx 포함
         setupFiles: ['./vitest.setup.ts'],                 // 신규
       },
       resolve: { alias: { '@': path.resolve(__dirname, '.') } },
     })
     ```
   - **`globals: false` 유지** — 본 phase 의 테스트는 `import { describe, it, expect, vi, beforeEach } from 'vitest'` 로 명시 import 한다. globals 를 켜면 기존 `report.test.ts` 의 명시 import 와 중복으로 혼동 가능.
   - `setupFiles` 만 신규 추가. 다른 옵션은 손대지 마라.

3. **`web/vitest.setup.ts` 신설**:
   - 내용 (한 줄):
     ```typescript
     import '@testing-library/jest-dom/vitest'
     ```
   - matcher (`toBeInTheDocument` 등) 등록 목적.

4. **신규 테스트 파일**: `web/__tests__/components/dashboard/DashboardV2.test.tsx`
   - 구조:
     ```typescript
     import { describe, it, expect, vi, beforeEach } from 'vitest'
     import { render, screen, waitFor } from '@testing-library/react'

     vi.mock('@/utils/supabase/client', () => {
         const chain: any = {}
         chain.from = vi.fn(() => chain)
         chain.select = vi.fn(() => chain)
         chain.in = vi.fn(() => chain)
         chain.eq = vi.fn(() => chain)
         chain.or = vi.fn(() => chain)
         chain.order = vi.fn(() => chain)
         chain.limit = vi.fn(() => Promise.resolve({ data: [], error: null }))
         return { supabase: chain }
     })

     vi.mock('@/utils/newArticleTracker', () => ({
         getLastVisitTime: vi.fn(() => null),
         updateLastVisitTime: vi.fn(),
         isArticleNew: vi.fn(() => false),
         countNewArticles: vi.fn(() => 0),
     }))

     // Header / SearchBar / DateSection / NewsCard 등은 실제 컴포넌트로 렌더해도 무방.
     // 단, ReportModal 은 portal/외부 의존이 있을 수 있으니 가벼운 mock 권장.
     vi.mock('@/components/ReportModal', () => ({
         default: () => null,
     }))

     describe('DashboardV2', () => {
         it('renders empty state when no articles', async () => {
             const DashboardV2 = (await import('@/components/dashboard/DashboardV2')).default
             render(<DashboardV2 />)
             await waitFor(() => {
                 expect(screen.getByText('검색 결과가 없습니다.')).toBeInTheDocument()
             })
         })
     })
     ```
   - **최소 1개 케이스**: empty state 노출.
   - 추가 케이스 (선택): 사이드바의 카테고리 버튼 클릭으로 currentCategory 가 변경되는지 (DOM 텍스트 변화로 검증).

5. **테스트 파일은 단일 파일로 충분**. 여러 파일을 만들지 마라. auth/proxy 테스트는 task 10 phase 3 의 몫.

## Acceptance Criteria

```bash
# 1) 신규 테스트 파일 존재
test -f web/__tests__/components/dashboard/DashboardV2.test.tsx

# 2) jsdom + @testing-library/react 가 설치되어 있는가
cd web && node -e "require('@testing-library/react')"
cd web && node -e "require('jsdom')"

# 3) vitest 환경 설정에 jsdom + .tsx include 가 모두 들어갔는가
grep -q "environment: 'jsdom'" web/vitest.config.ts
grep -q "test.{ts,tsx}" web/vitest.config.ts
test -f web/vitest.setup.ts

# 4) 빌드 + 테스트 통과 (기존 + 신규)
cd web && npm run build
cd web && npm run test

# 5) 신규 테스트가 1개 이상 통과하는지
cd web && npx vitest run __tests__/components/dashboard/DashboardV2.test.tsx
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/9-round7-dashboard-decomposition/index.json`의 phase 6 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
`@testing-library/react@^16.1.0` 이 vitest 1.6 또는 React 19 와 호환 충돌을 일으키는 경우 — 즉 vitest 자체를 2.x 로 올려야만 해결되는 경우 — phase 6 status 를 `error` 로 마킹하고 `error_message` 에 충돌 내용 + 충돌 버전 + "vitest upgrade is out of scope for phase 6" 를 기록하라. 사용자 결정 필요.

## 주의사항

- **production 코드 수정 금지**. `web/components/**/*.tsx` 는 phase 6 에서 건드리지 마라. 오직 신규 테스트 파일 + vitest config 부분 치환 + setup 신규 + package.json devDep 3 개 추가.
- `package.json` 에 devDep 추가는 정확히 3 개 (`@testing-library/react`, `@testing-library/jest-dom`, `jsdom`). 이미 있는 패키지는 다시 설치 금지.
- **vitest 자체 업그레이드 금지**. vitest `^1.6.0` 는 그대로. 2.x 로 올려야 풀리는 호환 문제는 phase 6 의 scope 가 아니다 — 즉시 error.
- `@testing-library/react` 는 **반드시 `^16.1.0` 이상**. 16.0.x 는 React 19 act import 변경으로 깨진다.
- `@/utils/supabase/client` 의 mock 은 chain 메서드 (`from / select / in / eq / or / order / limit`) 를 모두 흉내내야 한다. DashboardV2 의 `fetchArticles` 가 어떤 메서드를 호출하는지 먼저 확인 (`Promise.all` 안의 3 쿼리).
- `getLastVisitTime`, `updateLastVisitTime` mock 은 default null / no-op 로 두어 useEffect 의 setTimeout 이 그대로 돌아도 문제 없게 한다.
- `await waitFor(...)` 안에 assertion 을 넣어 fetch 가 끝날 때까지 기다린다. timeout 은 default (1000ms) 로 충분.
- ReportModal mock 은 `default: () => null` 한 줄. portal / Gemini 호출 / supabase update 등의 외부 의존성을 차단.
- `web/__tests__/components/dashboard/` 디렉토리가 없으면 새로 만든다.
- 시각적 회귀 (스타일, 레이아웃) 는 자동 검증 대상 아님 — 사용자 수동 회귀 체크리스트 참고 (spec/refactor-round6-roadmap.md §9.2).
