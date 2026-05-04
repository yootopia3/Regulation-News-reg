# 대시보드 Articles API 경계 축소 계획

> **범위:** 이 문서는 구현 전 계획이다. 이번 단계에서는 task/phase 파일을 만들지 않고, 코드 변경도 이 계획에 정의된 범위 안에서만 다음 단계에 진행한다.

## 목표

대시보드의 기존 화면과 사용자 흐름은 유지하면서 클라이언트로 내려가는 기사 데이터 경계를 보수적으로 줄인다.

1. `ReportModal`의 `react-hooks/exhaustive-deps` warning을 제거한다.
2. 대시보드 클라이언트가 받는 `analysis_result`를 카드 표시와 필터에 필요한 필드로 제한한다.
3. `DashboardV2`의 Supabase 직접 조회를 `/api/articles` 서버 route로 감싼다.

## 비목표

- DB schema, RLS, migration 변경 없음
- `/api/report` request contract 변경 없음: 클라이언트는 계속 `articleId`만 보낸다.
- 리포트 생성, 캐시, Gemini 호출 흐름 변경 없음
- 대시보드 정렬, 필터, 검색, NEW badge, 모바일 시간 표시 변경 없음
- 큰 구조 개편, 새 데이터 계층 추상화, shared package 분리 없음

## 현재 확인 사항

- `git status --short --branch`: `## main`
- `DashboardV2.tsx`는 `web/utils/supabase/client.ts`의 `supabase`를 직접 import하고 `articles`를 3개 카테고리로 조회한다.
- 현재 대시보드 조회 컬럼은 `id,title,agency,category,published_at,published_at_source,created_at,link,analysis_result,view_count,star_rating`이다.
- `content`는 이미 대시보드 클라이언트 조회에서 빠져 있다.
- 대시보드 컴포넌트가 실제로 쓰는 `analysis_result` 필드:
  - `summary`: `NewsCard` 확장 영역의 AI 요약
  - `importance_score`: 카드 점수, 낮은 점수 필터, 날짜/리스트 정렬
  - `keywords`: 검색 필터
- `risk_level`은 현재 카드 렌더링에서 직접 쓰지 않지만 요청된 safe shape에 포함되어 유지한다.
- `/api/report`는 현재 `articleId`만 검증하고 서버에서 `title`, `content`, `agency`, `analysis_result`를 조회한다. 이 흐름은 유지한다.
- `proxy.ts`는 `/api/*`를 `mp_session` 쿠키로 보호한다. `/api/articles`도 이 보호 범위에 들어간다.
- 현재 `web/utils/supabase/client.ts`는 `NEXT_PUBLIC_USE_V2_DB === 'true'`일 때 V2 URL/anon key를, 아니면 V1 URL/anon key를 사용한다. `/api/articles`도 기존 대시보드와 같은 DB를 보도록 이 선택 기준을 따른다.

## 응답 계약

`GET /api/articles`는 아래 형태만 반환한다.

```ts
type DashboardArticle = {
  id: string
  title: string
  agency: string
  category?: string | null
  published_at: string
  published_at_source?: 'source' | 'collected_fallback' | string | null
  created_at?: string | null
  link: string
  view_count?: number
  star_rating?: number | null
  analysis_result?: {
    summary?: string[]
    importance_score?: number
    risk_level?: string
    keywords?: string[]
  } | null
}

type ArticlesResponse = {
  articles: DashboardArticle[]
}
```

오류 응답은 `{ error: string }`와 적절한 HTTP status를 사용한다.

## 유지/제거 필드

`analysis_result`에서 유지:

- `summary`
- `importance_score`
- `risk_level`
- `keywords`

`analysis_result`에서 클라이언트 응답으로 내리지 않음:

- `detailed_report`
- `impact_analysis`
- `action_items`
- `report_generated_at`
- `filter_reason`
- `is_relevant`
- 그 외 카드 표시와 검색/정렬에 쓰지 않는 모든 JSONB 필드

top-level 응답에서 내리지 않음:

- `content`
- `embedding`
- `is_trending`
- DB 조회 mock이나 raw row에 섞일 수 있는 그 외 미허용 필드

## 파일 계획

| 파일 | 작업 |
|---|---|
| `web/components/ReportModal.tsx` | effect-local async 함수 또는 `useCallback`으로 hook dependency warning 제거 |
| `web/app/api/articles/route.ts` | 새 `GET` route 추가, 서버 Supabase 조회, 응답 sanitize |
| `web/components/dashboard/DashboardV2.tsx` | Supabase 직접 조회 제거, `/api/articles` fetch 사용 |
| `web/components/dashboard/NewsCard.tsx` | 필요 시 `Article` 타입만 응답 shape에 맞춰 보수적으로 보정 |
| `web/__tests__/api/articles.test.ts` | route sanitize와 Supabase error 테스트 추가 |
| `web/__tests__/proxy.test.ts` | `/api/articles`가 세션 없이 보호되는지 proxy 테스트 추가 |
| `web/__tests__/components/dashboard/DashboardV2.test.tsx` | Supabase mock을 fetch mock으로 변경 |

## 구현 계획

### 1. 기준선 조사

- 요청된 파일과 관련 테스트를 먼저 읽고 현재 동작 기준을 기록한다.
- 대시보드에서 `analysis_result` 사용 필드를 다시 `rg`로 확인한다.
- 구현 중 기존 기능 보존 기준:
  - 카테고리별 조회 조건 유지
  - `published_at desc` 기준 조회와 최종 merge 정렬 유지
  - 클라이언트의 검색, 필터, 그룹핑, NEW badge 계산 유지
  - `ReportModal`은 modal open + article id 존재 시에만 fetch

### 2. `ReportModal` hook warning 정리

- `useEffect` 내부에 `fetchReport` async 함수를 넣는 방식이 가장 좁은 변경 후보이다.
- dependency는 `isOpen`과 `article?.id` 중심으로 둔다.
- 닫힘 또는 article 없음 상태에서는 기존처럼 `report`를 `null`로 reset한다.
- loading/error 처리는 유지한다.
- 필요하면 effect cleanup guard로 닫힌 뒤 늦게 도착한 응답이 state를 덮지 않게 한다.
- `/api/report` 호출 payload는 계속 `{ articleId: String(article.id) }`만 사용한다.

### 3. `/api/articles` route 추가

- `web/app/api/articles/route.ts`에 `GET`을 추가한다.
- 인증은 `proxy.ts`의 `/api/*` 보호에 맡기고 route 내부에서 중복 구현하지 않는다.
- Supabase client는 route 내부에서 생성한다.
- key 선택:
  - URL 선택은 기존 대시보드 클라이언트와 동일하게 `NEXT_PUBLIC_USE_V2_DB === 'true'` 기준을 따른다.
  - V2 선택 시 `NEXT_PUBLIC_SUPABASE_URL_V2` / `NEXT_PUBLIC_SUPABASE_ANON_KEY_V2`를 사용한다.
  - V1 선택 시 `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`를 사용한다.
  - 조회 key는 `SUPABASE_SERVICE_ROLE_KEY`가 있으면 우선 사용하고, 없으면 선택된 DB의 anon key로 fallback한다.
  - 운영에서 `SUPABASE_SERVICE_ROLE_KEY`가 선택된 URL과 다른 프로젝트를 가리키면 안 된다. 이 mismatch는 env 설정 문제로 보고, local/test에서는 anon fallback으로 read path를 검증한다.
- 조회 조건은 현재 `DashboardV2`와 동일하게 유지한다.
  - press: `agency in pressAgencies`, `category = press_release OR category IS NULL`, `published_at desc`, `limit 1000`
  - regulation: `agency in regulationAgencies`, `category = regulation_notice`, `published_at desc`, `limit 1000`
  - sanction: `agency in sanctionAgencies`, `category = sanction_notice`, `published_at desc`, `limit 1000`
- 세 결과를 merge하고 `id` 기준 dedupe 후 `published_at desc`로 정렬한다.
- 응답 직전 모든 row를 whitelist와 런타임 타입 guard 기반으로 sanitize한다.
  - `analysis_result.summary`, `analysis_result.keywords`: `string[]`일 때만 유지한다.
  - `analysis_result.importance_score`: `number`일 때만 유지한다.
  - `analysis_result.risk_level`: `string`일 때만 유지한다.
  - 허용 key라도 타입이 맞지 않으면 기본값으로 보정하지 않고 생략한다.
- Supabase query error가 하나라도 있으면 로그를 남기고 `500 { error: 'Failed to fetch articles' }` 형태로 반환한다.
  - 현재 클라이언트 직접 조회는 부분 성공 데이터를 merge할 수 있지만, 새 서버 API는 사용자 요청의 “Supabase error 시 500 응답 확인”을 수용해 오류를 명확한 API 실패로 드러낸다.
  - 정상 성공 경로의 카테고리 조건, dedupe, 정렬, 필터 동작은 기존과 동일하게 유지한다.

### 4. `DashboardV2` 변경

- `supabase` import와 `DASHBOARD_ARTICLE_COLUMNS` 상수를 제거한다.
- `fetchArticles`는 `fetch('/api/articles')`를 호출하고 `{ articles }`만 `setArticles`에 반영한다.
- 실패 시 기존 수준처럼 `console.error`를 남기고 `loading`을 종료한다.
- 기존 `processedData` 로직은 유지한다.
- `ReportModal` 호출부와 `/api/report` 사용 방식은 건드리지 않는다.

### 5. 테스트 계획

- `web/__tests__/api/articles.test.ts`
  - safe top-level fields만 응답하는지 확인
  - `analysis_result`에서 `summary`, `importance_score`, `risk_level`, `keywords`만 유지되는지 확인
  - 허용된 `analysis_result` key라도 타입이 맞지 않으면 응답에서 생략되는지 확인
  - `content`, `detailed_report`, `impact_analysis`, `action_items`, `report_generated_at` 등이 제거되는지 확인
  - 세 category query가 기존 조건을 유지하는지 확인: agency list, category 조건, `published_at desc`, `limit(1000)`
  - 여러 category 결과 merge 후 `id` dedupe와 최종 `published_at desc` 정렬이 유지되는지 확인
  - Supabase query error 시 `500`과 `{ error: string }` 응답 확인
  - `NEXT_PUBLIC_USE_V2_DB`에 따른 V1/V2 URL/anon key 선택, service role key 우선 사용, anon fallback을 mock으로 확인한다.
- `web/__tests__/proxy.test.ts`
  - 세션 없이 `/api/articles` 요청 시 `401 { error: 'unauthorized' }`가 반환되는지 확인한다.
  - `/api/auth/login` 예외와 기존 비 API redirect 보호 흐름은 기존 테스트가 있다면 유지하고, 없다면 `/api/articles` 보호만 좁게 추가한다.
- `web/__tests__/components/dashboard/DashboardV2.test.tsx`
  - `@/utils/supabase/client` mock 제거
  - `global.fetch` mock으로 `/api/articles` 호출과 empty state 렌더링 확인
  - 기존 MAFRA constants 테스트는 유지
- 기존 `NewsCard` 시간 표시 테스트와 `/api/report` 테스트는 contract 변화 없이 통과해야 한다.

## 검증 계획

반드시 실행:

```bash
cd web && npm run lint
cd web && npm run test
cd web && npm run build
venv/bin/python -m pytest tests/unit -q
```

추가 확인:

```bash
rg "from\\('articles'\\).*select|select\\(DASHBOARD_ARTICLE_COLUMNS\\)|select\\(['\\\"]\\*['\\\"]\\)" web/components web/utils web/app -n
rg "content|detailed_report|impact_analysis|action_items|report_generated_at" web/app/api/articles web/__tests__ -n
```

기대:

- 대시보드 컴포넌트와 클라이언트 util에 직접 Supabase `articles` 조회가 남지 않는다.
- `/api/articles`와 `/api/report` 서버 route의 조회만 남는다.
- `/api/articles` 테스트에는 sanitize 대상 필드명이 명시적으로 등장한다.
- `/api/articles` route 응답 코드에는 미허용 필드를 내보내는 경로가 없다.

## 리스크와 보수적 대응

- `/api/articles`는 proxy를 거친 실제 runtime에서 보호된다. route handler 단위 테스트는 proxy를 통과하지 않으므로 인증 테스트로 해석하지 않는다.
- 서버 route가 DB에서 `analysis_result` 전체 JSONB를 읽더라도 클라이언트 응답은 whitelist sanitize를 통과한 값만 내려준다.
- `risk_level`은 현재 UI에서 직접 쓰지 않지만 요청된 shape와 향후 카드 표시 가능성을 고려해 유지한다.
- `Article` 타입 보정은 nullable 허용 범위만 넓히고 렌더링 동작은 바꾸지 않는다.
- 어떤 category query라도 실패하면 API는 500으로 실패한다. 기존 클라이언트는 부분 성공 데이터를 보여줄 수 있었지만, 요청된 API error 테스트 기준에 맞춰 서버 경계를 명확히 한다.
