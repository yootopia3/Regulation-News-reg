# Phase 1: report-modal-hooks

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 이해하라:

- `/home/pacer/projects/reg_brief/CLAUDE.md`
- `/home/pacer/projects/reg_brief/docs/ARCHITECTURE.md`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`
- `/home/pacer/projects/reg_brief/docs/superpowers/plans/2026-05-04-dashboard-articles-api-boundary.md`

그리고 아래 파일을 읽어 현재 ReportModal 흐름과 report API 계약을 확인하라:

- `/home/pacer/projects/reg_brief/web/components/ReportModal.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx`
- `/home/pacer/projects/reg_brief/web/app/api/report/route.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/api/report.test.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/components`

이전 phase의 작업물은 없다. 이 phase가 task 12의 첫 phase다.

## 작업 내용

목표: `ReportModal`의 `react-hooks/exhaustive-deps` warning만 보수적으로 정리한다.

1. `web/components/ReportModal.tsx`의 `useEffect`와 `fetchReport` 구조를 정리한다.
   - 가장 좁은 변경은 `useEffect` 내부에 async `fetchReport` 함수를 두는 방식이다.
   - `useCallback`을 써도 되지만, 불필요한 dependency 증가나 재요청 루프가 생기면 안 된다.
   - effect dependency는 `isOpen`과 `article?.id`처럼 실제 fetch 조건에 필요한 값만 포함한다.
   - 닫힘 상태 또는 `article` 없음 상태에서는 기존처럼 `report`를 `null`로 reset한다.
   - `loading`, error markdown, `console.error`, `finally` 기반 loading 해제 동작은 유지한다.

2. `/api/report` 호출 계약을 바꾸지 않는다.
   - body는 계속 `{ articleId: String(article.id) }`만 전송한다.
   - title, content, agency를 클라이언트에서 보내는 흐름을 만들지 않는다.

3. `ReportModal` component test를 추가하거나 보강한다.
   - 선호 경로: `web/__tests__/components/ReportModal.test.tsx`
   - modal open + article 존재 시 `/api/report`가 한 번 호출되는지 확인한다.
   - fetch body가 `{ articleId: '<id>' }`만 포함하는지 확인한다.
   - 같은 article로 rerender할 때 불필요한 중복 호출이 생기지 않는지 확인한다.
   - close 상태로 바뀌면 report content가 reset되는지 확인한다.
   - API error가 markdown error로 표시되고 loading이 종료되는지 확인한다.

4. 늦게 도착한 응답이 닫힌 modal state를 덮는 문제가 보이면 effect cleanup guard를 추가한다.
   - guard는 state update만 막고 fetch cancellation 같은 큰 구조 변경은 하지 않는다.

5. 이 phase에서는 DashboardV2, Supabase 조회, `/api/articles` route를 건드리지 않는다.

## Acceptance Criteria

```bash
# 1) hook lint warning 제거 확인
cd /home/pacer/projects/reg_brief/web && npm run lint

# 2) 기존 report API 테스트 유지
cd /home/pacer/projects/reg_brief/web && npm run test -- __tests__/api/report.test.ts

# 3) ReportModal component 동작 테스트
cd /home/pacer/projects/reg_brief/web && npm run test -- __tests__/components/ReportModal.test.tsx

# 4) /api/report payload 계약이 articleId-only인지 확인
cd /home/pacer/projects/reg_brief && rg "articleId: String\\(article\\.id\\)" web/components/ReportModal.tsx
cd /home/pacer/projects/reg_brief && ! rg "content:|title:|agency:" web/components/ReportModal.tsx
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/12-dashboard-api-boundary/index.json`의 phase 1 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- `/api/report` route, prompt, Gemini, cache write 흐름은 바꾸지 마라.
- modal UI, 문구, 버튼, print, close 동작을 바꾸지 마라.
- `article` 객체 전체를 dependency로 유지해서 lint warning을 숨기거나 재요청 루프를 만들지 마라.
- DB schema/RLS/migration을 변경하지 마라.
- 기존 테스트를 깨뜨리지 마라.
