# Phase 4: news-card-ui

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 이해하라:

- `/home/pacer/projects/reg_brief/CLAUDE.md`
- `/home/pacer/projects/reg_brief/docs/ARCHITECTURE.md`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`
- `/home/pacer/projects/reg_brief/.cross-review/20260504T040604Z/round_1/author_v2.md`

그리고 이전 phase의 작업물을 반드시 확인하라:

- `/home/pacer/projects/reg_brief/web/utils/date.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/utils/date.test.ts`
- `/home/pacer/projects/reg_brief/src/pipeline.py`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`

아래 frontend 파일과 테스트 구조를 직접 읽어 현재 UI 패턴에 맞춰 작업하라:

- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/DateSection.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/StarRating.tsx`
- `/home/pacer/projects/reg_brief/web/__tests__/components/dashboard/DashboardV2.test.tsx`
- `/home/pacer/projects/reg_brief/web/__tests__/components/dashboard/AgencyChipBar.test.tsx`

이전 phase에서 만든 `getArticleDisplayTime()`을 재사용하고, 같은 로직을 카드 안에 중복 구현하지 마라.

## 작업 내용

목표: 모바일 카드 오른쪽에 KST 기준 발행/수집 시각을 표시한다. 날짜 그룹핑, 정렬, NEW 배지 의미는 그대로 유지한다.

1. `web/components/dashboard/NewsCard.tsx`의 `Article` 타입을 확장한다.
   - `published_at_source?: 'source' | 'collected_fallback' | string | null`
   - 기존 필드는 제거하지 않는다.

2. 기존 `timeStr = new Date(article.published_at).toLocaleTimeString(...)` 로직을 제거한다.
   - phase 3의 `getArticleDisplayTime(article)`를 사용한다.
   - `displayTime.timeText`가 빈 문자열이면 시간 UI를 렌더하지 않는다.
   - `displayTime.label === '수집'`인 경우에만 작은 `수집` 라벨을 보인다.
   - `발행` 라벨은 기본 카드에서 보이지 않게 한다.

3. 카드 레이아웃을 모바일 중심으로 정리한다.
   - 현재 header의 왼쪽 컨텐츠 영역에는 `min-w-0`를 준다.
   - 오른쪽 컬럼은 `shrink-0`, `min-w-[64px]` 또는 그에 준하는 고정 최소폭을 둔다.
   - 오른쪽 컬럼 순서:
     1. `HH:mm`
     2. fallback이면 `수집`
     3. 기존 `StarRating`
     4. 기존 chevron
   - 기존 기관 배지, 세부 카테고리 배지, NEW 배지는 왼쪽 meta row에 유지한다.
   - 카드 전체의 expand/click 동작과 원문/AI 보고서 버튼 stopPropagation 동작을 유지한다.

4. `web/__tests__/components/dashboard/NewsCard.test.tsx`를 추가한다.
   - `published_at_source: 'source'` row는 KST `HH:mm`을 표시하고 `수집` 라벨을 표시하지 않는다.
   - `published_at_source: 'collected_fallback'` row는 `created_at` 기준 KST `HH:mm`과 `수집` 라벨을 표시한다.
   - `published_at_source: null` 또는 누락 row는 legacy처럼 `published_at` 기준 KST `HH:mm`을 표시한다.
   - NEW 배지는 기존처럼 `article.isNew`가 true일 때 표시된다.
   - invalid/missing 날짜 row는 `Invalid Date`, 빈 시간 placeholder, `수집` 라벨을 표시하지 않고 제목과 기본 카드 내용은 정상 렌더링한다.
   - 긴 한국어 제목과 NEW 배지를 가진 fallback row를 렌더링해 왼쪽 영역에 `min-w-0`, 오른쪽 컬럼에 `shrink-0`가 적용되고 시간, `수집`, 별점, chevron 순서가 유지되는지 검증한다.

5. `DashboardV2.tsx`, `DateSection.tsx`, `newArticleTracker.ts`는 필요한 타입 호환 외에는 바꾸지 않는다.
   - 날짜 그룹핑은 `published_at` 기준 유지.
   - 날짜 내 정렬은 기존 중요도 후 `published_at` 기준 유지.
   - NEW 판정은 기존 `created_at || published_at` 기준 유지.

## Acceptance Criteria

```bash
# 1) NewsCard가 shared helper를 사용
grep -q "getArticleDisplayTime" web/components/dashboard/NewsCard.tsx
! grep -q "toLocaleTimeString" web/components/dashboard/NewsCard.tsx

# 2) 날짜 그룹핑/정렬 정책 유지
grep -q "toKSTDate(article.published_at)" web/components/dashboard/DashboardV2.tsx
grep -q "new Date(b.published_at)" web/components/dashboard/DateSection.tsx
grep -q "created_at || article.published_at" web/components/dashboard/DashboardV2.tsx

# 3) frontend tests/build
cd web && npm run test -- NewsCard date DashboardV2
cd web && npm run lint
cd web && npm run build
```

추가 모바일 레이아웃 확인:

- 가능하면 로컬 dev server 또는 Story/테스트 fixture로 390px 폭에서 긴 한국어 제목, 기관/카테고리/NEW 배지, fallback `수집` 라벨이 함께 있는 카드를 확인하라.
- 브라우저 자동화가 가능한 환경이면 screenshot을 남기고, 불가능하면 `NewsCard.test.tsx`에서 레이아웃 관련 class/order 검증을 강화한 뒤 phase output에 “browser screenshot unavailable”을 기록하라.
- 어떤 경우에도 오른쪽 시간 컬럼이 제목/배지와 겹치는 상태를 알고도 completed 처리하지 마라.

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/11-mobile-time-display/index.json`의 phase 4 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- UI에 timestamp 선택 비즈니스 로직을 중복 작성하지 마라. `web/utils/date.ts` helper를 사용한다.
- 카드 안에 긴 설명 문구를 추가하지 마라. fallback일 때만 짧게 `수집`을 표시한다.
- 날짜 섹션과 리스트 정렬을 `created_at` 기준으로 바꾸지 마라.
- 기존 `NEW` badge 위치와 의미를 바꾸지 마라.
- 카드 오른쪽 컬럼이 제목 영역을 밀어내거나 겹치지 않도록 `min-w-0`와 `shrink-0` 제약을 반드시 둔다.
- invalid date 상태에서 `Invalid Date`, `NaN`, 빈 시간용 시각 wrapper가 사용자에게 보이지 않게 하라.
