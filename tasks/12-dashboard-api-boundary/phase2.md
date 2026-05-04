# Phase 2: articles-api

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 이해하라:

- `/home/pacer/projects/reg_brief/CLAUDE.md`
- `/home/pacer/projects/reg_brief/docs/ARCHITECTURE.md`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`
- `/home/pacer/projects/reg_brief/docs/superpowers/plans/2026-05-04-dashboard-articles-api-boundary.md`

그리고 이전 phase의 작업물을 반드시 확인하라:

- `/home/pacer/projects/reg_brief/web/components/ReportModal.tsx`
- `/home/pacer/projects/reg_brief/tasks/12-dashboard-api-boundary/index.json`

아래 소스와 테스트를 직접 읽고 현재 패턴에 맞춰 작업하라:

- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/constants.ts`
- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/DateSection.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/useHasNewByCategory.ts`
- `/home/pacer/projects/reg_brief/web/app/api/report/route.ts`
- `/home/pacer/projects/reg_brief/web/proxy.ts`
- `/home/pacer/projects/reg_brief/web/utils/supabase/client.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/api/report.test.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/proxy.test.ts`

## 작업 내용

목표: 대시보드 article 조회를 감쌀 `GET /api/articles` route를 추가하고, 응답 sanitize와 보호 흐름을 테스트한다. 이 phase에서는 `DashboardV2`가 아직 이 API를 사용하지 않아도 된다.

1. `web/app/api/articles/route.ts`를 새로 만든다.
   - `GET`만 구현한다.
   - route 내부에서 Supabase client를 생성한다.
   - 인증은 `proxy.ts`의 `/api/*` 보호에 맡기고, route 내부에서 별도 세션 검증을 중복 구현하지 않는다.
   - DB schema, RLS, migration은 변경하지 않는다.

2. Supabase env 선택 기준을 명확히 구현한다.
   - `NEXT_PUBLIC_USE_V2_DB === 'true'`이면 `NEXT_PUBLIC_SUPABASE_URL_V2`와 `NEXT_PUBLIC_SUPABASE_ANON_KEY_V2`를 선택한다.
   - 그 외에는 `NEXT_PUBLIC_SUPABASE_URL`와 `NEXT_PUBLIC_SUPABASE_ANON_KEY`를 선택한다.
   - 조회 key는 `SUPABASE_SERVICE_ROLE_KEY`가 있으면 우선 사용하고, 없으면 선택된 DB의 anon key를 fallback으로 사용한다.
   - URL 또는 사용 가능한 key가 없으면 `500 { error: string }`를 반환한다.

3. 기존 `DashboardV2`의 세 category 조회 조건을 route에 이식한다.
   - agency list는 가능하면 `web/components/dashboard/constants.ts`의 `pressAgencies`, `regulationAgencies`, `sanctionAgencies`를 import해 재사용한다.
   - press:
     - `.in('agency', pressAgencies)`
     - `.or('category.eq.press_release,category.is.null')`
     - `.order('published_at', { ascending: false })`
     - `.limit(1000)`
   - regulation:
     - `.in('agency', regulationAgencies)`
     - `.eq('category', 'regulation_notice')`
     - `.order('published_at', { ascending: false })`
     - `.limit(1000)`
   - sanction:
     - `.in('agency', sanctionAgencies)`
     - `.eq('category', 'sanction_notice')`
     - `.order('published_at', { ascending: false })`
     - `.limit(1000)`
   - select 컬럼은 현재 대시보드의 top-level 안전 컬럼과 `analysis_result`만 사용한다:
     - `id,title,agency,category,published_at,published_at_source,created_at,link,analysis_result,view_count,star_rating`
   - `view_count`와 `analysis_result.risk_level`은 현재 UI에서 직접 렌더링하지 않지만, 사용자 요청의 `/api/articles` 응답 shape에 명시되어 있으므로 유지한다. 이 둘 외에 현재 카드/필터/정렬 또는 요청 shape에 없는 필드는 추가하지 않는다.

4. 결과를 기존과 같은 방식으로 합친다.
   - 세 결과를 merge한다.
   - `id` 기준으로 dedupe한다.
   - 최종 배열은 `published_at` 내림차순으로 정렬한다.
   - Supabase query error가 하나라도 있으면 `console.error`를 남기고 `500 { error: 'Failed to fetch articles' }`를 반환한다.
   - 기존 클라이언트 직접 조회는 부분 성공 데이터를 merge할 수 있었지만, 이번 task의 사용자 요구에 “Supabase error 시 500 응답 확인”이 명시되어 있으므로 새 서버 API는 all-or-nothing 실패 계약을 따른다.

5. 응답은 항상 whitelist와 런타임 타입 guard를 통과시킨다.
   - top-level 유지 필드:
     - `id`, `title`, `agency`, `category`, `published_at`, `published_at_source`, `created_at`, `link`, `view_count`, `star_rating`
   - top-level runtime guard:
     - 필수 string 필드 `id`, `title`, `agency`, `published_at`, `link` 중 하나라도 string이 아니면 해당 article 전체를 응답에서 제외한다.
     - 선택 필드 `category`, `published_at_source`, `created_at`은 string 또는 null일 때만 유지하고, 그 외 타입이면 생략한다.
     - 선택 numeric 필드 `view_count`, `star_rating`은 number 또는 null일 때만 유지하고, 그 외 타입이면 생략한다.
   - `analysis_result` 유지 필드:
     - `summary`: `string[]`일 때만 유지
     - `importance_score`: `number`일 때만 유지
     - `risk_level`: `string`일 때만 유지
     - `keywords`: `string[]`일 때만 유지
   - 허용 key라도 타입이 맞지 않으면 기본값으로 보정하지 말고 생략한다.
   - `analysis_result`에 유지 가능한 key가 하나도 없으면 `analysis_result`는 `null` 또는 생략 중 하나로 일관되게 처리하고, 테스트 기대값도 그 선택에 맞춘다.
   - `content`, `embedding`, `is_trending`, `detailed_report`, `impact_analysis`, `action_items`, `report_generated_at`, `filter_reason`, `is_relevant`는 응답에 포함하지 않는다.
   - route 구현은 whitelist 기반이어야 한다. 금지 필드명을 route 코드에 denylist/comment로 나열하지 말고, 테스트 fixture에서만 금지 필드 제거를 검증한다.
   - 성공 응답 shape는 `{ articles: Article[] }`만 사용한다.

6. 테스트를 추가/수정한다.
   - `web/__tests__/api/articles.test.ts`를 추가한다.
     - safe top-level fields만 응답하는지 확인한다.
     - 필수 top-level 필드 타입이 잘못된 row는 article 전체가 drop되는지 확인한다.
     - 선택 top-level 필드 타입이 잘못되면 해당 field만 생략되는지 확인한다.
     - `analysis_result` safe fields만 유지되는지 확인한다.
     - 허용 key라도 타입이 틀리면 생략되는지 확인한다.
     - `content`, `detailed_report`, `impact_analysis`, `action_items`, `report_generated_at` 등이 제거되는지 확인한다.
     - 세 category query의 agency list, category 조건, `published_at desc`, `limit(1000)`이 유지되는지 mock으로 확인한다.
     - 여러 category 결과 merge 후 `id` dedupe와 최종 `published_at desc` 정렬이 유지되는지 확인한다.
     - Supabase error 시 `500`과 `{ error: string }` 응답을 확인한다.
     - V1/V2 env 선택, service role key 우선 사용, anon fallback을 mock으로 확인한다.
   - 기존 `web/__tests__/proxy.test.ts`에 `/api/articles` 세션 없음 요청이 `401 { error: 'unauthorized' }`인지 좁게 추가한다.

## Acceptance Criteria

```bash
# 1) 새 route와 테스트 존재
test -f /home/pacer/projects/reg_brief/web/app/api/articles/route.ts
test -f /home/pacer/projects/reg_brief/web/__tests__/api/articles.test.ts

# 2) route focused tests
cd /home/pacer/projects/reg_brief/web && npm run test -- __tests__/api/articles.test.ts __tests__/proxy.test.ts

# 3) sanitize 대상 필드가 테스트 fixture/assertion에 명시됨
cd /home/pacer/projects/reg_brief && rg "content|detailed_report|impact_analysis|action_items|report_generated_at" web/__tests__/api/articles.test.ts -n

# 4) route가 wildcard select 또는 금지 필드를 직접 노출하지 않음
cd /home/pacer/projects/reg_brief && ! rg "select\\(['\\\"]\\*['\\\"]\\)" web/app/api/articles -n
cd /home/pacer/projects/reg_brief && ! rg "content|embedding|is_trending|detailed_report|impact_analysis|action_items|report_generated_at|filter_reason|is_relevant" web/app/api/articles/route.ts -n
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/12-dashboard-api-boundary/index.json`의 phase 2 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- `DashboardV2`를 이 phase에서 `/api/articles`로 전환하지 마라. 전환은 phase 3에서 한다.
- `/api/report`의 request/response contract를 바꾸지 마라.
- service role key를 클라이언트로 노출하지 마라.
- DB schema/RLS/migration을 변경하지 마라.
- sanitize는 key whitelist만으로 끝내지 말고 런타임 타입을 확인하라.
- 기존 테스트를 깨뜨리지 마라.
