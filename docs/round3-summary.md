# Round 3 — Housekeeping Summary

## 범위

Round 1/2 이후 남은 housekeeping. 4개 축. 동작 변경 0, DB 스키마 변경 0,
프롬프트 문장 변경 0, 트리거 메커니즘 변경 0.

## 한 일

- **Dead code 제거**: `src/scheduler.py` 삭제. `requirements.txt`에서
  `apscheduler` 의존성 제거. 호출 경로가 사실 0건이었음을 확인 후 제거.
- **`scripts/` 정리**:
  - 루트 중복 `scripts/reanalyze_null_articles.py` 삭제
    (`scripts/admin/reanalyze_null_articles.py`가 정식 버전).
  - one-shot 유틸 4개 → `scripts/archive/round2/oneoff-tools/`.
  - v2 마이그레이션 6개 → `scripts/archive/round2/v2-migration/`.
  - `scripts/v2_schema_setup.sql`, `scripts/admin/**`, `scripts/monitor/**`
    유지.
- **Docs stale sweep**:
  - `docs/implementation_plan.md`, `docs/task.md` →
    `docs/archive/round0/stage4/`.
  - `docs/MASTER_CONTEXT.md`, `docs/PRD.md`, `docs/REQUIREMENTS.md`,
    `docs/ARCHITECTURE.md`, `spec/backend-architecture.md`에서 `scheduler.py`
    언급 제거.
  - `feat/v2.0-upgrade` 브랜치 언급 제거 (브랜치는 Round 2 마무리 시 삭제됨).
  - **운영 트리거 현실 정정**: collector는 GitHub Actions native cron이
    아니라 external cron-job.org → `workflow_dispatch on
    news_collector_v2_active.yml`. Watchdog만 GitHub Actions native cron
    사용 (`0 */2 * * *`, 2h 주기).
  - `MASTER_CONTEXT.md` 버전 1.1.0, `Last Updated 2026-04-08`.
- **GH Actions Node 20 deprecation 대응**:
  - `actions/checkout@v3` → `actions/checkout@v4`
  - `actions/setup-python@v4` → `actions/setup-python@v5`
  - 대상: `news_collector.yml`, `news_collector_v2_active.yml`, `watchdog.yml`.
  - **트리거 블록·주석·환경변수·job 이름·로직 모두 불변.** 버전 라인만 교체.
  - `ci.yml`은 Round 2에서 이미 `@v4`/`@v5`라 제외.

## 미룬 것

- `pipeline.py` 추가 책임 경계 정리 (DedupCache / CollectorRegistry).
- `_load_existing_links` 전체 페이지네이션 → batch-in 쿼리 (관측 후 결정).
- `list_scraper` 병렬화 (실측 1m 31s, 불필요).
- `web/components/dashboard/DashboardV2.tsx` 추가 분해 (이미 1차 분해 완료).
- Gemini SDK 교체 (`google.generativeai` → `google.genai`).
- backend ↔ frontend 프롬프트 내용 통합.
- git history rewrite (rotate-only 전략 유지).
- DB 스키마/인덱스 변경.
