# Phase 8: docs-sync

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `docs/ARCHITECTURE.md` (현재 본문. Round 1 이전 상태일 가능성 — 직접 확인)
- `spec/refactor-round1.md`
- `CLAUDE.md`

그리고 아래 파일을 직접 읽어 Round 2에서 바뀐 구조를 파악하라:

- `src/pipeline.py`
- `src/collectors/scraper.py` (facade)
- `src/collectors/` 하위 모듈
- `src/services/analyzer/` 하위 모듈
- `src/config/agency_loader.py` (Phase 6 결과)
- `src/config/settings.py` (Phase 7 결과)
- `web/app/api/report/route.ts` (Phase 5 결과)
- `web/lib/prompts/report.ts` (Phase 5 결과)
- `web/lib/validation/report.ts` (Phase 5 결과)
- `.github/workflows/ci.yml` (Phase 2/3/4 결과)
- `tests/` (Phase 3/6/7 결과)

이전 phase 산출물 전반.

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **문서를 Round 2 변경사항에 맞춰 패치 수준으로 갱신**한다. 전체 rewrite 금지 (결정 #8).

### 1. `docs/ARCHITECTURE.md` 패치

현재 본문을 읽고, 아래 변경사항만 반영하라. 기존 문장·섹션 구조·스타일을 최대한 유지.

- **Collectors**: `src/collectors/scraper.py`가 facade이며 실제 구현은 `http.py`, `date_parser.py`, `pagination.py`, `list_scraper.py`, `content_scraper.py`, `sanction_scraper.py`로 분해되어 있음을 반영 (이미 반영돼 있으면 건드리지 마라).
- **Analyzer**: `src/services/analyzer/`가 `gemini_client`, `prompts`, `hybrid`, `safeguards`, `result_mapper`로 분해되어 있음.
- **Agency metadata**: `SANCTION_AGENCY_CODES`가 `src/config/agency_loader.get_sanction_codes()`로 `agencies.json`의 `category` 필드에서 런타임 유도됨. 기존 하드코딩 frozenset 설명은 제거.
- **Gemini model IDs**: `GEMINI_FILTER_MODEL`, `GEMINI_ANALYZER_MODEL`, `GEMINI_ANALYZER_FALLBACK_MODEL` env로 backend 모델 ID가 주도됨. `GEMINI_REPORT_MODEL` env로 frontend `/api/report`의 모델이 주도됨. 기본값은 각각 `src/config/settings.py`와 `web/app/api/report/route.ts`의 fallback.
- **`/api/report`**: 요청 body는 `{ articleId }`만 수락. 서버가 Supabase에서 title/content/agency를 직접 조회. 프롬프트는 `web/lib/prompts/report.ts`의 `buildReportPrompt()`로 분리. `web/middleware.ts`가 세션 쿠키(`mp_session`)로 `/api/*`를 보호한다는 기존 사실도 1줄로 기재(이미 있으면 유지).
- **Tests / CI**: `tests/unit/**` pytest + `web/__tests__/**` vitest가 `.github/workflows/ci.yml`에서 PR 이벤트에 실행됨. secret scan은 `gitleaks` job.
- **`src/scheduler.py`**: 여전히 legacy (이번 라운드에서 제거 안 됨 — 결정 #10). 이미 legacy 표기가 있으면 유지.

**하지 말 것**:

- 문서 전체 rewrite.
- 섹션 순서 대규모 재배치.
- 새 스크린샷 추가.
- Round 1 이전 히스토리 기록 삭제.
- 프론트 대분해/성능 개선 계획 같은 Round 2 scope 밖 내용 추가.

### 2. `docs/round2-summary.md` 신규

Round 2에서 한 것과 미룬 것을 짧게 정리한다. 1~2 페이지 분량.

템플릿:

```markdown
# Round 2 — Hygiene & Integrity Summary

## 범위

저장소 위생 + 시크릿 도구화 + `/api/report` 입력 무결성 + 다중 소스 3축(모델 ID / report prompt / sanction rule) 단일화 + 최소 테스트 하네스(pytest + vitest).

동작 변경 0건, DB 스키마 변경 0건, 프롬프트 문장 변경 0건.

## 한 일

- **위생**: 루트 dump 삭제, `docs/*.resolved*`/`*.metadata.json`/스크린샷 `docs/archive/round0/`로 이동, `scripts/debug/` `scripts/archive/debug-round0/`로 이동, `web/check_*.js` 삭제, `.gitignore` scoped 패턴 추가, `.env.example` 2개 생성.
- **시크릿 도구**: gitleaks pre-commit + GitHub Actions job. `docs/secret-rotation-checklist.md` 추가. 실제 rotate는 사용자 수동 수행.
- **테스트 하네스**: pytest(`tests/unit/**`), vitest(`web/__tests__/**`), `.github/workflows/ci.yml`에 python-test/web-test/gitleaks 3 job.
- **`/api/report`**: body schema `{ articleId }`로 축소, 서버가 DB에서 title/content/agency 조회, 프롬프트 분리, 입력 무결성 테스트 green.
- **다중 소스 3축**:
  1. `SANCTION_AGENCY_CODES` → `agencies.json.category` 파생 (`src/config/agency_loader.py`).
  2. Gemini 모델 ID → env (`GEMINI_FILTER_MODEL`, `GEMINI_ANALYZER_MODEL`, `GEMINI_ANALYZER_FALLBACK_MODEL`, `GEMINI_REPORT_MODEL`).
  3. Report prompt → `web/lib/prompts/report.ts`로 분리.

## 미룬 것

- git history rewrite (rotate-only 전략).
- `web/components/DashboardV2.tsx` 분해 및 프런트 대규모 재설계.
- `list_scraper` 병렬화 (관측 후 결정).
- `_load_existing_links` 풀스캔 개선 (관측 후 결정).
- Sanction dedup 폴백 false positive 관측 로깅.
- `src/pipeline.py` 책임 경계 추가 정리 (`DedupCache`, `CollectorRegistry`).
- DB 스키마/인덱스 변경.
- `src/scheduler.py` 제거 (legacy 여부 후속 라운드에서 재판정).
- backend/frontend 프롬프트 내용 공유화.

## 시크릿 노출 이력

`web/.env.local`이 커밋 `89c8750` → `5b029d3` 사이 tracked 상태. 약 20분. rotate 체크리스트는 `docs/secret-rotation-checklist.md` 참조.
```

### 3. Round 1 문서 건드리지 않음

`spec/refactor-round1.md`는 역사 문서다. 수정 금지.

## Acceptance Criteria

```bash
test -f docs/round2-summary.md
# ARCHITECTURE.md에 Round 2 핵심 키워드가 존재
grep -q 'agency_loader' docs/ARCHITECTURE.md
grep -q 'GEMINI_ANALYZER_MODEL' docs/ARCHITECTURE.md
grep -q 'buildReportPrompt\|web/lib/prompts/report' docs/ARCHITECTURE.md
# round2-summary.md 핵심 섹션
grep -q '한 일' docs/round2-summary.md
grep -q '미룬 것' docs/round2-summary.md
grep -q '89c8750' docs/round2-summary.md
grep -q '5b029d3' docs/round2-summary.md
# Round 1 문서 무변경
git diff --quiet HEAD -- spec/refactor-round1.md
# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
# pytest / web test 회귀 없음
python -m pytest -q
cd web && npm test && npm run build
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 8 status를 `"completed"`로 변경.

`docs/ARCHITECTURE.md`에 핵심 키워드가 이미 존재해 grep이 통과하더라도, 내용이 실제 Round 2 결과와 맞는지 눈으로 확인하라. 문서가 거짓말을 하면 이 phase의 목적이 무너진다.

3회 이상 실패 시 `"error"` + `error_message`. 사용자 개입 필요 시 `"blocked"`.

## 주의사항

- **전체 rewrite 금지.** 기존 `docs/ARCHITECTURE.md`의 문장·구조를 최대한 보존하고, Round 2 변경점만 patch하라.
- **새 스크린샷 추가 금지.**
- **`docs/archive/round0/` 내부 파일 건드리지 마라.** 이미 이동된 역사 기록.
- **`spec/refactor-round1.md` 수정 금지.**
- **`src/`, `web/`, `config/`, `.github/workflows/`, `tests/` 수정 금지.** 이번 phase는 문서만.
- **`CLAUDE.md`, `README.md` 수정 금지.** 사용자 소유.
- `docs/secret-rotation-checklist.md`에 실제 키 값·해시·JWT 조각을 절대 기록하지 마라 (Phase 2에서도 동일 규칙).
- 기존 테스트·빌드를 깨지 마라.
