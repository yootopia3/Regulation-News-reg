# Phase 3: frontend-time-helper

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 이해하라:

- `/home/pacer/projects/reg_brief/CLAUDE.md`
- `/home/pacer/projects/reg_brief/docs/ARCHITECTURE.md`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`
- `/home/pacer/projects/reg_brief/.cross-review/20260504T040604Z/round_1/author_v2.md`

그리고 이전 phase의 작업물을 반드시 확인하라:

- `/home/pacer/projects/reg_brief/src/config/agency_codes.py`
- `/home/pacer/projects/reg_brief/src/pipeline.py`
- `/home/pacer/projects/reg_brief/src/collectors/rss_parser.py`
- `/home/pacer/projects/reg_brief/src/collectors/list_scraper.py`
- `/home/pacer/projects/reg_brief/src/collectors/sanction_scraper.py`
- `/home/pacer/projects/reg_brief/tasks/11-mobile-time-display/index.json`

아래 frontend 파일과 테스트 구조를 직접 읽어 현재 패턴에 맞춰 작업하라:

- `/home/pacer/projects/reg_brief/web/utils/date.ts`
- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx`
- `/home/pacer/projects/reg_brief/web/utils/newArticleTracker.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/utils/mafraLink.test.ts`
- `/home/pacer/projects/reg_brief/web/vitest.config.ts`

이 phase는 shared date helper까지만 만든다. 카드 UI 배치는 phase 4에서 수행한다.

## 작업 내용

목표: 카드가 사용할 KST display-time helper를 `web/utils/date.ts`에 추가하고, 날짜 그룹핑/정렬/NEW 배지는 기존 동작을 유지한다.

1. `web/utils/date.ts`에 타입과 helper를 추가한다.
   - type:
     ```ts
     export type PublishedAtSource = 'source' | 'collected_fallback' | null | undefined
     export type ArticleDisplayTime = {
       timeText: string
       label: '발행' | '수집' | null
       source: 'published' | 'collected' | 'unknown'
     }
     ```
   - helper signature:
     ```ts
     export function formatKSTTime(dateStr?: string | null): string
     export function getArticleDisplayTime(article: {
       published_at?: string | null
       created_at?: string | null
       published_at_source?: PublishedAtSource | string
     }): ArticleDisplayTime
     ```

2. helper 동작을 고정한다.
   - `formatKSTTime()`은 `Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hour12: false })`를 사용한다.
   - invalid/missing date는 빈 문자열을 반환한다.
   - `published_at_source === 'collected_fallback'`이면 `created_at`을 먼저 시도하고, 실패하면 `published_at`을 재시도한다.
   - fallback row에서 표시 가능한 시간이 있으면 `label: '수집'`, `source: 'collected'`를 반환한다.
   - `published_at_source === 'source'`, `null`, `undefined`, 알 수 없는 문자열은 legacy-safe하게 `published_at`을 표시한다.
   - `published_at`도 invalid면 `timeText: ''`, `label: null`, `source: 'unknown'`을 반환한다.
   - 기본 카드 UI에서는 `label: '발행'`을 표시하지 않을 예정이므로, source/legacy row는 `label: null`이어도 된다. 타입에는 미래 확장과 테스트 명확성을 위해 `'발행'`을 남겨둔다.

3. 기존 `toKSTDate()`와 `formatDateTitle()` 동작을 깨뜨리지 않는다.
   - `DashboardV2.tsx` 날짜 그룹핑은 기존처럼 `toKSTDate(article.published_at)`를 계속 사용해야 한다.
   - `DateSection.tsx` 정렬도 기존처럼 `published_at` 기준을 유지한다.

4. `web/__tests__/utils/date.test.ts`를 추가한다.
   - UTC ISO 문자열이 KST `HH:mm`으로 표시되는지 검증한다.
   - `source` row는 `published_at`을 선택하는지 검증한다.
   - `collected_fallback` row는 `created_at`을 선택하고 `수집` 라벨을 반환하는지 검증한다.
   - fallback row에서 `created_at` invalid면 `published_at`으로 재시도하는지 검증한다.
   - 둘 다 invalid이면 빈 `timeText`, `label: null`, `source: 'unknown'`인지 검증한다.
   - 알 수 없는 `published_at_source`는 legacy row처럼 `published_at`을 표시하는지 검증한다.

## Acceptance Criteria

```bash
# 1) helper exports 존재
grep -q "export function formatKSTTime" web/utils/date.ts
grep -q "export function getArticleDisplayTime" web/utils/date.ts
grep -q "ArticleDisplayTime" web/utils/date.ts

# 2) timezone 강제
grep -q "Asia/Seoul" web/utils/date.ts

# 3) frontend tests
cd web && npm run test -- date
cd web && npm run lint
cd web && npm run build
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/11-mobile-time-display/index.json`의 phase 3 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- `DashboardV2.tsx`의 날짜 그룹핑/정렬을 `created_at` 기준으로 바꾸지 마라.
- `newArticleTracker.ts`의 NEW 판정 기준을 바꾸지 마라.
- 브라우저 로컬 timezone에 맡기는 `toLocaleTimeString('ko-KR')`를 새 helper에 사용하지 마라. 반드시 `timeZone: 'Asia/Seoul'`을 명시한다.
- 카드 UI 변경은 phase 4에서 한다. 이 phase에서는 `NewsCard.tsx`의 레이아웃을 바꾸지 마라.
