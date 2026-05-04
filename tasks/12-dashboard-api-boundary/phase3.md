# Phase 3: dashboard-fetch

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 이해하라:

- `/home/pacer/projects/reg_brief/CLAUDE.md`
- `/home/pacer/projects/reg_brief/docs/ARCHITECTURE.md`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`
- `/home/pacer/projects/reg_brief/docs/superpowers/plans/2026-05-04-dashboard-articles-api-boundary.md`

그리고 이전 phase의 작업물을 반드시 확인하라:

- `/home/pacer/projects/reg_brief/web/components/ReportModal.tsx`
- `/home/pacer/projects/reg_brief/web/app/api/articles/route.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/api/articles.test.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/proxy.test.ts`
- `/home/pacer/projects/reg_brief/tasks/12-dashboard-api-boundary/index.json`

아래 대시보드 소스와 테스트를 직접 읽고 현재 UI 동작을 유지하라:

- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/DateSection.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/useHasNewByCategory.ts`
- `/home/pacer/projects/reg_brief/web/components/dashboard/constants.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/components/dashboard/DashboardV2.test.tsx`
- `/home/pacer/projects/reg_brief/web/__tests__/components/dashboard/NewsCard.test.tsx`
- `/home/pacer/projects/reg_brief/web/__tests__/components/dashboard/AgencyChipBar.test.tsx`

## 작업 내용

목표: `DashboardV2`가 Supabase 클라이언트를 직접 사용하지 않고 `/api/articles`에서 sanitized article 목록을 가져오도록 전환한다.

1. `web/components/dashboard/DashboardV2.tsx`를 수정한다.
   - `@/utils/supabase/client` import를 제거한다.
   - `DASHBOARD_ARTICLE_COLUMNS` 상수를 제거한다.
   - `fetchArticles`는 `fetch('/api/articles')`를 호출한다.
   - 성공 응답은 `{ articles }` shape만 기대하고 `setArticles(articles || [])`에 준하는 방식으로 반영한다.
   - `res.ok`가 아니면 `{ error }`를 읽을 수 있을 때 읽고 `console.error`를 남긴다.
   - 실패해도 `loading`은 반드시 종료한다.
   - 기존 client-side filtering/search/date grouping/NEW badge/category/agency 선택 동작은 유지한다.
   - `ReportModal` 호출부와 `/api/report` 호출 흐름은 바꾸지 않는다.

2. 타입을 보수적으로 맞춘다.
   - 필요하면 `web/components/dashboard/NewsCard.tsx`의 `Article` 타입에서 nullable 범위만 API 응답 shape에 맞춰 넓힌다.
   - 새 추상화 파일을 만들지 말고, 필요한 최소 타입 보정만 한다.
   - UI 렌더링 문구, 정렬 기준, 모바일 시간 표시 helper 호출은 바꾸지 않는다.

3. `web/__tests__/components/dashboard/DashboardV2.test.tsx`를 fetch mock 기반으로 바꾼다.
   - `@/utils/supabase/client` mock을 제거한다.
   - `global.fetch` 또는 `vi.stubGlobal('fetch', ...)`로 `/api/articles` 응답을 mock한다.
   - empty state 렌더링을 유지 검증한다.
   - `/api/articles`가 호출되는지 확인한다.
   - 기존 MAFRA constants 테스트는 유지한다.
   - 필요하면 fetch 실패 시 empty state 또는 loading 종료를 검증하되, UI 문구는 기존 범위를 벗어나 바꾸지 않는다.

4. 직접 Supabase 조회가 남지 않도록 확인한다.
   - 대시보드 컴포넌트와 client util에서 `articles` 직접 조회가 남지 않아야 한다.
   - `/api/articles`와 `/api/report` 서버 route의 Supabase 조회는 허용된다.

## Acceptance Criteria

```bash
# 1) Dashboard focused tests
cd /home/pacer/projects/reg_brief/web && npm run test -- __tests__/components/dashboard/DashboardV2.test.tsx __tests__/components/dashboard/NewsCard.test.tsx __tests__/components/dashboard/AgencyChipBar.test.tsx

# 2) API route focused tests도 계속 통과
cd /home/pacer/projects/reg_brief/web && npm run test -- __tests__/api/articles.test.ts __tests__/api/report.test.ts __tests__/proxy.test.ts

# 3) lint
cd /home/pacer/projects/reg_brief/web && npm run lint

# 4) 대시보드의 직접 Supabase articles 조회 제거 확인
cd /home/pacer/projects/reg_brief && ! rg "select\\(DASHBOARD_ARTICLE_COLUMNS\\)" web/components web/utils web/app -n
cd /home/pacer/projects/reg_brief && ! rg "from\\('articles'\\)" web/components web/utils -n
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/12-dashboard-api-boundary/index.json`의 phase 3 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- `web/utils/supabase/client.ts` 파일 자체를 삭제하지 마라. 다른 코드가 사용할 수 있으므로 대시보드 조회 import만 제거한다.
- 화면 구조, 정렬, 필터, NEW badge, AgencyChipBar, DateSection sticky 동작, 모바일 시간 표시를 바꾸지 마라.
- `/api/report` 호출 payload를 바꾸지 마라.
- DB schema/RLS/migration을 변경하지 마라.
- 기존 테스트를 깨뜨리지 마라.
