# Round 2 — Hygiene & Integrity Summary

## 범위

저장소 위생 + 시크릿 도구화 + `/api/report` 입력 무결성 + 다중 소스 3축(모델 ID / report prompt / sanction rule) 단일화 + 최소 테스트 하네스(pytest + vitest).

동작 변경 0건, DB 스키마 변경 0건, 프롬프트 문장 변경 0건.

## 한 일

- **위생**: 루트 dump 삭제, `docs/*.resolved*` / `*.metadata.json` / 스크린샷을 `docs/archive/round0/`로 이동, `scripts/debug/`를 `scripts/archive/debug-round0/`로 이동, `web/check_*.js` 삭제, `.gitignore`에 scoped 패턴 추가, `.env.example` 2개 생성 (repo root + `web/`).
- **시크릿 도구**: gitleaks pre-commit hook + GitHub Actions `gitleaks` job. `docs/secret-rotation-checklist.md` 추가. 실제 키 rotate는 사용자가 수동 수행.
- **테스트 하네스**: pytest (`tests/unit/**`), vitest (`web/__tests__/**`). `.github/workflows/ci.yml`에 `python-test` / `web-test` / `gitleaks` 3 job이 PR 이벤트에서 실행.
- **`/api/report`**: 요청 body schema를 `{ articleId }`로 축소 (`web/lib/validation/report.ts`). 서버가 Supabase에서 `title` / `content` / `agency`를 직접 조회. 프롬프트는 `web/lib/prompts/report.ts`의 `buildReportPrompt()`로 분리. 입력 무결성 테스트 green.
- **다중 소스 3축**:
  1. `SANCTION_AGENCY_CODES` → `agencies.json`의 `category` 필드에서 파생 (`src/config/agency_loader.get_sanction_codes()`).
  2. Gemini 모델 ID → env 단일화 (`GEMINI_FILTER_MODEL`, `GEMINI_ANALYZER_MODEL`, `GEMINI_ANALYZER_FALLBACK_MODEL`, `GEMINI_REPORT_MODEL`). 기본값은 `src/config/settings.py`와 `web/app/api/report/route.ts`의 fallback.
  3. Report prompt → `web/lib/prompts/report.ts`로 분리.

## 미룬 것

- git history rewrite (rotate-only 전략).
- `web/components/dashboard/DashboardV2.tsx` 분해 및 프런트 대규모 재설계.
- `list_scraper` 병렬화 (관측 후 결정).
- `_load_existing_links` 풀스캔 개선 (관측 후 결정).
- Sanction dedup 폴백 false positive 관측 로깅.
- `src/pipeline.py` 책임 경계 추가 정리 (`DedupCache`, `CollectorRegistry`).
- DB 스키마 / 인덱스 변경.
- `src/scheduler.py` 제거 (legacy 여부 후속 라운드에서 재판정).
- backend / frontend 프롬프트 내용 공유화.

## 시크릿 노출 이력

`web/.env.local`이 커밋 `89c8750` → `5b029d3` 사이 tracked 상태였다. 약 20분. rotate 절차는 `docs/secret-rotation-checklist.md` 참조.
