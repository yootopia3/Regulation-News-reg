# Phase 4: final-verification

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 이해하라:

- `/home/pacer/projects/reg_brief/CLAUDE.md`
- `/home/pacer/projects/reg_brief/docs/ARCHITECTURE.md`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`
- `/home/pacer/projects/reg_brief/docs/superpowers/plans/2026-05-04-dashboard-articles-api-boundary.md`

그리고 이전 phase의 작업물을 반드시 확인하라:

- `/home/pacer/projects/reg_brief/web/components/ReportModal.tsx`
- `/home/pacer/projects/reg_brief/web/app/api/articles/route.ts`
- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx`
- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx`
- `/home/pacer/projects/reg_brief/web/__tests__/api/articles.test.ts`
- `/home/pacer/projects/reg_brief/web/__tests__/components/dashboard/DashboardV2.test.tsx`
- `/home/pacer/projects/reg_brief/web/__tests__/proxy.test.ts`
- `/home/pacer/projects/reg_brief/tasks/12-dashboard-api-boundary/index.json`

## 작업 내용

목표: 전체 검증을 실행하고 남은 회귀나 누락을 최소 수정한다. 이 phase는 새 기능을 추가하는 단계가 아니라 최종 안정화 단계다.

1. 전체 필수 검증을 실행한다.
   - `cd web && npm run lint`
   - `cd web && npm run test`
   - `cd web && npm run build`
   - `venv/bin/python -m pytest tests/unit -q`

2. 추가 `rg` 검증을 실행한다.
   - 대시보드 컴포넌트/클라이언트 util에 직접 Supabase `articles` 조회가 남지 않았는지 확인한다.
   - `/api/articles`와 테스트에 sanitize 대상 필드명이 명시되어 있는지 확인한다.
   - `/api/articles` route에서 금지 필드를 응답으로 내보내는 경로가 없는지 확인한다.

3. 실패가 있으면 최소 수정한다.
   - test/lint/build 실패 원인을 정확히 확인하고, task 범위 안의 코드만 수정한다.
   - DB schema/RLS/migration 변경으로 해결하지 않는다.
   - UI 디자인이나 화면 문구를 임의로 바꾸지 않는다.
   - 새로운 abstraction이나 큰 refactor를 추가하지 않는다.

4. 최종 결과를 task index에 기록한다.
   - 모든 검증이 통과하면 phase 4를 `"completed"`로 변경한다.
   - 검증 일부를 환경 문제로 실행하지 못했다면 `"blocked"`로 변경하고 `blocked_reason`에 실행 불가 사유를 명확히 적는다.
   - 검증 실패가 task 범위 안에서 해결되지 않으면 `"error"`와 `error_message`를 기록한다.

## Acceptance Criteria

```bash
# 1) 필수 검증
cd /home/pacer/projects/reg_brief/web && npm run lint
cd /home/pacer/projects/reg_brief/web && npm run test
cd /home/pacer/projects/reg_brief/web && npm run build
cd /home/pacer/projects/reg_brief && venv/bin/python -m pytest tests/unit -q

# 2) 대시보드 직접 Supabase articles 조회 제거 확인
cd /home/pacer/projects/reg_brief && ! rg "from\\('articles'\\)|select\\(DASHBOARD_ARTICLE_COLUMNS\\)|select\\(['\\\"]\\*['\\\"]\\)" web/components web/utils -n

# 3) 서버 route 조회는 허용되며 sanitize 테스트가 존재해야 함
cd /home/pacer/projects/reg_brief && rg "from\\('articles'\\)" web/app/api/articles web/app/api/report -n
cd /home/pacer/projects/reg_brief && rg "content|detailed_report|impact_analysis|action_items|report_generated_at" web/__tests__/api/articles.test.ts web/__tests__/api/report.test.ts -n
cd /home/pacer/projects/reg_brief && ! rg "content|embedding|is_trending|detailed_report|impact_analysis|action_items|report_generated_at|filter_reason|is_relevant" web/app/api/articles/route.ts -n

# 4) ReportModal은 articleId-only report payload 유지
cd /home/pacer/projects/reg_brief && rg "articleId: String\\(article\\.id\\)" web/components/ReportModal.tsx
cd /home/pacer/projects/reg_brief && ! rg "content:|title:|agency:" web/components/ReportModal.tsx
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/12-dashboard-api-boundary/index.json`의 phase 4 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- 이 phase에서 새 요구사항을 추가하지 마라. 검증 실패를 고치는 최소 변경만 허용된다.
- DB schema/RLS/migration을 변경하지 마라.
- `/api/report` contract를 바꾸지 마라.
- 대시보드 화면, 정렬, 필터, NEW badge, 모바일 시간 표시, 리포트 생성 흐름을 바꾸지 마라.
- 기존 테스트를 깨뜨리지 마라.
