# Phase 7: Regression Verify

코드 변경 없음. 회귀 체크리스트와 AC를 직접 검증하고 결과를 기록한다.

## 사전 준비

설계 의도:

- `spec/refactor-round1.md` — §4 회귀 체크리스트, §6 AC
- `spec/backend-architecture.md`

이전 phase 산출물 전체:

- `src/config/settings.py`, `src/config/agency_codes.py`
- `src/db/client.py` (lazy)
- `src/services/analyzer/*`
- `src/collectors/*`
- `src/pipeline.py` (slim)

## 작업 내용

### 7.1 정적 검증

다음을 모두 직접 실행하고 결과를 캡처하라:

```bash
# import 사이드 이펙트 0건 (의존성은 사용자가 사전 설치한 상태 가정)
env -u SUPABASE_URL -u SUPABASE_ANON_KEY -u GEMINI_API_KEY \
  python -c "from src.pipeline import Pipeline"
env -u SUPABASE_URL -u SUPABASE_ANON_KEY -u GEMINI_API_KEY \
  python -c "from src.services.analyzer import HybridAnalyzer, RegulationAnalyzer"

# agency 코드 문자열 리터럴 0건
! grep -rEn "'(FSS_SANCTION|FSS_MGMT_NOTICE)'" src/pipeline.py

# diff 0건 확인 (out of scope 항목) — phase 1에서 기록한 baseline commit 기준
BASELINE=$(cat tasks/1-backend-structure/baseline-commit.txt)
test -n "$BASELINE"
git diff --stat "$BASELINE" -- web/ config/agencies.json .github/ scripts/ db/
```

`git diff --stat "$BASELINE" -- <paths>` 의 출력이 비어 있어야 한다 (변경 0).
출력이 있으면 회귀로 간주하고 phase status 를 `"error"` 로 설정하라.

### 7.2 AC 결과 기록

`tasks/1-backend-structure/regression-report.md` 파일을 새로 만들어 다음 내용을
적어라:

- 각 AC 항목과 통과/실패 결과
- `wc -l` 결과 (`spec/refactor-round1.md` §7 권장 목표치 대비, 정보용):
  - `src/pipeline.py`
  - `src/services/analyzer/hybrid.py`
  - `src/collectors/list_scraper.py`
  - `src/collectors/sanction_scraper.py`
  - `src/collectors/content_scraper.py`
  - 미달이어도 phase 실패 처리 금지. 기록만 한다.
- baseline commit hash 와 diff 결과 요약
- import 사이드 이펙트 검증 결과
- 외부 인터페이스 보존 확인:
  - `from src.pipeline import Pipeline` ✓
  - `from src.services.analyzer import HybridAnalyzer` ✓
  - `from src.services.analyzer import RegulationAnalyzer` ✓
  - `from src.services.notifier import TelegramNotifier` ✓
  - `from src.collectors.rss_parser import collect_all_rss` ✓
  - `from src.collectors.scraper import ContentScraper` ✓
  - `from src.db.client import supabase, get_supabase_client` ✓
- 회귀 체크리스트(`spec/refactor-round1.md` §4) 각 항목 상태. 자동 검증 가능한
  것은 직접 실행, `.env`가 필요한 항목(`python src/main.py` 1사이클)은
  **"수동 검증 필요 — runner 환경에서 실행 불가"**로 표기.

### 7.3 동작 회귀가 의심되는 부분 점검

다음 두 항목은 코드 grep으로 확인:

1. analyzer 결과 dict 키 셋 — `result_mapper.parse_analyze_response`가 반환하는
   키가 다음과 정확히 일치하는지: `summary`, `impact_analysis`, `action_items`,
   `risk_level`, `risk_score`, `risk_tags`, `pillars`, `analyzed_by`.
2. `process()` 가 반환하는 dict가 다음 키를 포함하는지: `is_relevant`,
   `importance_score`, `filter_status`, `analysis_status` + (analyzed인 경우 위
   8개 키).

확인 결과를 regression-report.md에 적어라.

## Acceptance Criteria

```bash
test -f tasks/1-backend-structure/regression-report.md
grep -q "Pipeline" tasks/1-backend-structure/regression-report.md
grep -q "HybridAnalyzer" tasks/1-backend-structure/regression-report.md
grep -q "회귀 체크리스트" tasks/1-backend-structure/regression-report.md

# 최종 빌드 검증 (import smoke test)
python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
```

## AC 검증 방법

위 명령 모두 통과 시 phase 7 status를 `"completed"` 로 변경하라.

자동으로 검증 불가능한 항목(`python src/main.py` 1사이클 실제 실행)은 통과 처리
하지 말고 regression-report.md에 **"수동 검증 대기"** 로 명시하라. 사용자가 별도
환경에서 검증한다.

3회 실패 시 `"error"` + `error_message`.

## 주의사항

- 코드 변경 금지. 이번 phase는 검증과 보고서 작성만.
- 검증 중 회귀가 발견되면 phase status를 `"error"`로 두고, regression-report.md에
  발견 사항을 상세히 적어라. 임의로 코드를 수정해 회귀를 가리지 마라.
- diff 비교는 반드시 `tasks/1-backend-structure/baseline-commit.txt` 에 기록된
  hash 기준으로 한다. `origin/main` 이나 `HEAD~N` 같이 환경에 의존하는 기준은
  사용하지 마라. 파일이 없으면 phase 1이 잘못된 것이므로 `"error"` 처리하고
  보고하라.
- `web/`, `agencies.json`, `db/schema.sql`, `.github/`, `scripts/` diff는 0이어야 한다.
