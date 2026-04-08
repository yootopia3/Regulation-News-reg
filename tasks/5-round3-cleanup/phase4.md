# Phase 4: gh-actions-upgrade

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `docs/round2-summary.md` (Round 2가 deprecation 대응을 후속 라운드로 미룬 맥락)
- `docs/ARCHITECTURE.md` (Phase 3 patch 결과 — 트리거 서술이 정정된 상태)
- `docs/PRD.md` (Phase 3 patch 결과 — `Status` 필드는 아직 "Stage 2 Complete")
- `CLAUDE.md`

핵심 워크플로 (이번 phase 수정 대상):

- `.github/workflows/news_collector.yml` (v1 legacy, dispatch-only)
- `.github/workflows/news_collector_v2_active.yml` (active production collector)
- `.github/workflows/watchdog.yml` (active health-check)

핵심 워크플로 (수정 금지, 비교용):

- `.github/workflows/ci.yml` (Round 2 산출물, 이미 `actions/checkout@v4` + `actions/setup-python@v5` + `actions/setup-node@v4`. **이 파일은 손대지 마라**)

사전 검증 — 현재 버전 라인을 직접 눈으로 확인:

```bash
grep -nE 'actions/checkout@|actions/setup-python@' \
  .github/workflows/news_collector.yml \
  .github/workflows/news_collector_v2_active.yml \
  .github/workflows/watchdog.yml \
  .github/workflows/ci.yml
```

이전 phase 산출물:

- Phase 1: `src/scheduler.py` 삭제, `apscheduler` 제거
- Phase 2: `scripts/` 루트 정리
- Phase 3: docs/spec stale sweep + 운영 트리거 사실 정정. **`PRD.md`의 `Status` 필드는 아직 "Stage 2 Complete" 상태**, **`docs/round3-summary.md`는 아직 존재하지 않음** — 이번 phase에서 최종화한다.

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 두 가지를 한다:

1. **GH Actions Node 20 deprecation 대응** — action 버전 라인만 교체. 트리거 블록·주석·환경변수·job 이름·step 구조 모두 불변.
2. **Round 3 finalization** — `docs/round3-summary.md` 신규 작성 + `docs/PRD.md`의 `Status` 필드 최종화. 이 phase가 성공해야만 Round 3가 "끝났다"는 신호가 docs에 박힌다.

### 4-1. `news_collector.yml` upgrade (v1 legacy)

- `uses: actions/checkout@v3` → `uses: actions/checkout@v4`
- `uses: actions/setup-python@v4` → `uses: actions/setup-python@v5`

다른 모든 라인 보존:

- `# DISABLED: Using v2 collector now (news_collector_v2_active.yml)` 주석
- `# schedule:` 주석
- `# - cron: '5,35 * * * *'` 주석
- `workflow_dispatch:` 라인
- `# Allow manual trigger only` 주석
- 환경변수, `python-version`, `python src/main.py` 호출, job 이름

### 4-2. `news_collector_v2_active.yml` upgrade (production)

- `uses: actions/checkout@v3` → `@v4`
- `uses: actions/setup-python@v4` → `@v5`

**트리거 블록 절대 보존**:

- `# Schedule disabled - using external cron (cron-job.org)` 주석
- `# schedule:` 주석
- `# - cron: '*/15 * * * *'` 주석
- `workflow_dispatch:` 라인
- `# Keep this for cron-job.org and manual triggers` 주석

**환경변수 절대 보존**: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ENV_TYPE`. 각 env가 매핑되는 secret 이름(`secrets.NEXT_PUBLIC_SUPABASE_URL_V2` 등)도 그대로.

`timeout-minutes`, `python-version`, `python src/main.py` 호출, job 이름 보존.

### 4-3. `watchdog.yml` upgrade

- `uses: actions/checkout@v3` → `@v4`
- `uses: actions/setup-python@v4` → `@v5`

**트리거 블록 절대 보존**:

- `schedule:` (활성 — phase 3 patch에서 ARCHITECTURE/PRD에 "GitHub Actions native cron"으로 명시한 그 트리거)
- `- cron: '0 */2 * * *'`
- `# Run every 2 hours` 주석
- `workflow_dispatch:` 라인

step 순서·job 이름·env 보존.

### 4-4. `ci.yml` 무변경

- `git diff --quiet HEAD -- .github/workflows/ci.yml` 통과해야 한다.
- 이미 `@v4` / `@v5`를 사용 중이라 추가 작업 없음.

### 4-5. `docs/PRD.md` Status 필드 최종화

본문에서 한 줄만 정정:

```
- **Status**: Stage 2 Complete
+ **Status**: Round 3 Cleanup Complete
```

다른 줄은 손대지 마라.

### 4-6. `docs/round3-summary.md` 신규 작성

Round 2 summary와 동일 톤·구조. 다음 템플릿 그대로 사용해도 되고, 사실관계를 유지하면서 다듬어도 된다.

```markdown
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
  - `actions/checkout@v3` → `@v4`
  - `actions/setup-python@v4` → `@v5`
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
```

### 4-7. 다른 파일 수정 금지

- `.github/workflows/ci.yml` — 무변경
- `src/`, `web/`, `tests/`, `scripts/`, `requirements.txt`, `requirements-dev.txt` — 무변경
- `docs/MASTER_CONTEXT.md`, `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md` — 이번 phase에서 손대지 마라 (phase 3에서 이미 patch 완료)
- `docs/SCHEMA.md`, `docs/round2-summary.md` — 무변경
- `spec/backend-architecture.md`, `spec/refactor-round1.md` — 무변경

## Acceptance Criteria

```bash
# 3개 워크플로의 action 버전 업그레이드 확인
for f in .github/workflows/news_collector.yml \
         .github/workflows/news_collector_v2_active.yml \
         .github/workflows/watchdog.yml; do
  if grep -q 'actions/checkout@v3' "$f"; then echo "FAIL: $f still has checkout@v3"; exit 1; fi
  if grep -q 'actions/setup-python@v4' "$f"; then echo "FAIL: $f still has setup-python@v4"; exit 1; fi
  grep -q 'actions/checkout@v4' "$f" || { echo "FAIL: $f missing checkout@v4"; exit 1; }
  grep -q 'actions/setup-python@v5' "$f" || { echo "FAIL: $f missing setup-python@v5"; exit 1; }
done

# ci.yml 무변경 (Round 2 상태 유지)
git diff --quiet HEAD -- .github/workflows/ci.yml
grep -q 'actions/checkout@v4' .github/workflows/ci.yml
grep -q 'actions/setup-python@v5' .github/workflows/ci.yml

# 트리거 블록 / 주석 / 환경변수 / 진입점 보존 검증
grep -q '# Schedule disabled - using external cron (cron-job.org)' .github/workflows/news_collector_v2_active.yml
grep -q '# Keep this for cron-job.org and manual triggers' .github/workflows/news_collector_v2_active.yml
grep -q '# DISABLED: Using v2 collector now' .github/workflows/news_collector.yml
grep -q "cron: '0 \*/2 \* \* \*'" .github/workflows/watchdog.yml
grep -q '# Run every 2 hours' .github/workflows/watchdog.yml

grep -q 'NEXT_PUBLIC_SUPABASE_URL_V2' .github/workflows/news_collector_v2_active.yml
grep -q 'NEXT_PUBLIC_SUPABASE_ANON_KEY_V2' .github/workflows/news_collector_v2_active.yml
grep -q 'GEMINI_API_KEY' .github/workflows/news_collector_v2_active.yml
grep -q 'TELEGRAM_BOT_TOKEN' .github/workflows/news_collector_v2_active.yml
grep -q 'TELEGRAM_CHAT_ID' .github/workflows/news_collector_v2_active.yml
grep -q 'ENV_TYPE' .github/workflows/news_collector_v2_active.yml
grep -q 'python src/main.py' .github/workflows/news_collector_v2_active.yml

# Round 3 finalization
test -f docs/round3-summary.md
grep -q '한 일' docs/round3-summary.md
grep -q '미룬 것' docs/round3-summary.md
grep -q 'cron-job\.org' docs/round3-summary.md
grep -q 'scheduler\.py' docs/round3-summary.md
grep -q 'actions/checkout@v4' docs/round3-summary.md

grep -q '\*\*Status\*\*: Round 3 Cleanup Complete' docs/PRD.md
! grep -q '\*\*Status\*\*: Stage 2 Complete' docs/PRD.md
# merge 상태 단정 표현 금지 (feature branch에서 phase가 돌므로)
! grep -qi 'merged to main' docs/PRD.md
! grep -qi 'merged to main' docs/round3-summary.md

# Phase 3가 이미 patch한 파일들은 이 phase에서 추가 변경되지 않았어야 함
# (PRD.md는 Status 한 줄만 더 변경되었으므로 PRD.md는 제외)
git diff --name-only HEAD -- docs/MASTER_CONTEXT.md docs/REQUIREMENTS.md docs/ARCHITECTURE.md spec/backend-architecture.md 2>/dev/null
test "$(git diff --name-only HEAD -- docs/MASTER_CONTEXT.md docs/REQUIREMENTS.md docs/ARCHITECTURE.md spec/backend-architecture.md 2>/dev/null | wc -l)" = "0"

# scripts/v2_schema_setup.sql, scripts/admin, scripts/monitor 무변경
git diff --quiet HEAD -- scripts/v2_schema_setup.sql scripts/admin scripts/monitor

# 임포트 / pytest 회귀 0
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
python3 -m pytest -q

# web 회귀 (npm ci 필수)
cd web && npm ci && npm test && npm run build
cd -
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 4 status를 `"completed"`로 변경하고, 자동으로 task 전체 완료 처리된다 (`tasks/index.json`의 `id: 5` status가 `"completed"`로).

3회 이상 실패 시 `"error"` + `error_message`. 사용자 개입 필요 시 `"blocked"`.

## 주의사항

- **이번 phase의 yaml 변경은 action 버전 라인 6개뿐.** (3개 파일 × 2 라인). 다른 yaml 변경 일체 금지.
- **트리거 블록 절대 보존**: `schedule:` 블록 (주석 처리/활성 상관없이), `workflow_dispatch:`, 모든 주석 한 글자도 바꾸지 마라.
- **환경변수, secret 참조, job 이름, `timeout-minutes`, `python-version`, step 순서 모두 불변.**
- **`ci.yml` 수정 금지.** Round 2 산출물. 이미 `@v4`/`@v5`.
- **`@v5+`, `@v6+` 같은 더 최신 버전 시도 금지.** Round 2 ci.yml과 동일하게 `checkout@v4`, `setup-python@v5`로 통일.
- **새 step 추가 금지** (cache, retry 등).
- **`schedule:` 블록을 부활시키지 마라.** Production collector는 의도적으로 `schedule:`이 disabled이고 external cron-job.org가 트리거한다.
- **`docs/round3-summary.md` 외에 새 docs 파일 생성 금지.**
- **`docs/PRD.md`의 Status 라인 외에 PRD 본문 수정 금지.** Phase 3에서 이미 다른 라인은 patch했고, 이 phase가 그 patch를 되돌리거나 추가로 손대면 책임 경계가 깨진다.
- **`docs/MASTER_CONTEXT.md`, `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `spec/backend-architecture.md`는 이 phase에서 수정 금지.** Phase 3가 책임지는 파일들이다.
- **phase 1, 2, 3 산출물 되돌리지 마라.**
- 기존 pytest/vitest를 깨뜨리지 마라.
