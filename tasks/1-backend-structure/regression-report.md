# Backend Structure Refactor — Regression Report (Phase 7)

- Baseline commit: `8ef023a9d8b57530ce3b0dc51a19320495168d8a`
  (`docs: create backend-structure plan`, recorded in `baseline-commit.txt`)
- HEAD at verify time: `fabf2cd513a3127bcc42b9224f817ecb5298255f`

## 1. Acceptance Criteria (spec/refactor-round1.md §6)

| # | AC | Result |
|---|---|---|
| 1 | `pip install -r requirements.txt` 성공 | **수동 검증 대기** (runner 환경에서 사전 수행됨을 가정) |
| 2 | `from src.pipeline import Pipeline` 사이드 이펙트 없이 통과 | **PASS** |
| 3 | `from src.services.analyzer import HybridAnalyzer` 사이드 이펙트 없이 통과 | **PASS** |
| 4 | `python src/main.py` 1사이클 정상 종료, 9 agency 처리 로그 | **수동 검증 대기 — runner 환경에서 실행 불가 (.env 필요)** |
| 5 | 회귀 체크리스트 전부 통과 | §4 참조 (자동 가능 항목 PASS, .env 의존 항목 수동 대기) |
| 6 | agency 코드 문자열 리터럴 0건 (enum/상수만 사용) | **PASS** (`src/pipeline.py`에 `'FSS_SANCTION'` / `'FSS_MGMT_NOTICE'` 리터럴 0건) |
| 7 | DB 스키마 diff 0건 | **PASS** (`git diff --stat $BASELINE -- db/` → 비어 있음) |
| 8 | `web/`, `config/agencies.json`, `.github/`, `scripts/`, 루트 dump 파일 diff 0건 | **PASS** |

### Out-of-scope diff 명령/결과

```
BASELINE=8ef023a9d8b57530ce3b0dc51a19320495168d8a
git diff --stat "$BASELINE" -- web/ config/agencies.json .github/ scripts/ db/
# (empty output — 변경 0건)
```

## 2. Import Side-Effect 검증

`.env` 와 3개 필수 환경변수(`SUPABASE_URL`, `SUPABASE_ANON_KEY`,
`GEMINI_API_KEY`)를 모두 언셋한 상태에서 실행:

```
env -u SUPABASE_URL -u SUPABASE_ANON_KEY -u GEMINI_API_KEY \
  python -c "from src.pipeline import Pipeline"
env -u SUPABASE_URL -u SUPABASE_ANON_KEY -u GEMINI_API_KEY \
  python -c "from src.services.analyzer import HybridAnalyzer, RegulationAnalyzer"
```

- `Pipeline` import: **PASS** (무경고)
- `HybridAnalyzer`, `RegulationAnalyzer` import: **PASS**
  - 한 번의 `FutureWarning` 이 출력되는데 이는 `google.generativeai` 패키지 자체가
    import 시 발행하는 deprecation 경고이다. 현재 pipeline/analyzer 모듈의 사이드
    이펙트가 아니며, baseline 에서도 동일하게 발생한다. 설계상 허용 범위.
  - `genai.configure(...)` 와 `logging.basicConfig(...)` 는 import 경로에서
    호출되지 않음 (`hybrid.py` 는 `GeminiClient` 를 지연 생성, `configure` 는
    `GeminiClient.__init__` 에서만 호출).

## 3. 외부 인터페이스 보존

아래 import가 모두 성공함을 단일 프로세스에서 확인:

- `from src.pipeline import Pipeline` ✓
- `from src.services.analyzer import HybridAnalyzer` ✓
- `from src.services.analyzer import RegulationAnalyzer` ✓
- `from src.services.notifier import TelegramNotifier` ✓
- `from src.collectors.rss_parser import collect_all_rss` ✓
- `from src.collectors.scraper import ContentScraper` ✓
- `from src.db.client import supabase, get_supabase_client` ✓

## 4. 회귀 체크리스트 (spec/refactor-round1.md §4)

| # | 항목 | 검증 수단 | 결과 |
|---|---|---|---|
| 1 | `pip install -r requirements.txt` 통과 | 환경 외부 | **수동 검증 대기** |
| 2 | `from src.pipeline import Pipeline` 사이드 이펙트 없이 통과 | 자동 | **PASS** |
| 3 | `from src.services.analyzer import HybridAnalyzer` import 시 `genai.configure` / `logging.basicConfig` 호출 안 됨 | 자동 | **PASS** (hybrid.py 는 `GeminiClient` 를 `__init__` 에서 생성, import 단계에서는 호출 없음; `logging.basicConfig` 는 `src/main.py` 의 `__main__` 가드 뒤에만 위치) |
| 4 | `python src/main.py` 1사이클 정상 종료, 9 agency 처리 | `.env` 필요 | **수동 검증 필요 — runner 환경에서 실행 불가** |
| 5 | 새 article 1건 이상 DB 저장 | `.env` + Supabase 필요 | **수동 검증 필요 — runner 환경에서 실행 불가** |
| 6 | 제재 중복 체크가 동일 `examMgmtNo`+`emOpenSeq` 필터링 | 코드 검토 | **PASS** — `src/pipeline.py:170-184` `_is_duplicate` 가 `SANCTION_AGENCY_CODES` 분기 후 `extract_sanction_key(link)` 로 `(agency, examMgmtNo, emOpenSeq)` 튜플을 생성하여 `sanction_keys` 세트에 대해 검사. 링크 단위 fallback 도 유지. |
| 7 | Telegram 메시지 포맷 동일 | 코드 검토 | **PASS** — pipeline 은 `notifier.format_and_send(agency, title, link, analysis_result)` 서명만 사용하며 notifier 모듈은 이번 라운드에서 변경 없음. |
| 8 | 분석 결과 JSON 키 셋 동일 | 코드 검토 | **PASS** — 아래 §5 참조 |

## 5. 동작 회귀 점검

### 5.1 `parse_analyze_response` 결과 키 셋

`src/services/analyzer/result_mapper.py:30-40` 의 반환 dict 키:

```
summary, impact_analysis, action_items,
risk_level, risk_score, risk_tags, pillars, analyzed_by
```

→ phase 스펙 요구 8개 키와 **정확히 일치** (PASS).

### 5.2 `HybridAnalyzer.process()` 반환 dict 키 셋

`src/services/analyzer/hybrid.py:105-142` 분석:

- 기본 반환 키: `is_relevant`, `importance_score`, `filter_status` (항상 포함).
- Tier 2 가 실행된 경우 `result.update(analysis)` 로 위 8개 키 병합 + 이후
  `analysis_status` 가 `"ANALYZED"` / `"ANALYSIS_FAILED"` / `"SKIPPED"` 중 하나로
  반드시 세팅됨.
- 따라서 non-analyzed 경로에서는 `is_relevant`, `importance_score`,
  `filter_status`, `analysis_status` 4개를 포함하고, analyzed 경로에서는 여기에
  8개 분석 키가 추가되어 총 12개 (spec 요구와 동일).

**PASS**.

### 5.3 agency 코드 문자열 리터럴 검사

```
grep -rEn "'(FSS_SANCTION|FSS_MGMT_NOTICE)'" src/pipeline.py
# (매칭 없음)
```

→ `pipeline.py` 는 `SANCTION_AGENCY_CODES` (from `src.config.agency_codes`)
상수만 사용. PASS.

## 6. LOC (spec/refactor-round1.md §7 — 정보용)

| 파일 | LOC | 권장 목표치 | 상태 |
|---|---|---|---|
| `src/pipeline.py` | 318 | < 180 | 미달 (정보용, phase 실패 처리 없음) |
| `src/services/analyzer/hybrid.py` | 142 | < 200 | 충족 |
| `src/collectors/list_scraper.py` | 152 | < 200 | 충족 |
| `src/collectors/sanction_scraper.py` | 201 | < 200 | 근접 초과 (정보용) |
| `src/collectors/content_scraper.py` | 58 | < 200 | 충족 |

`pipeline.py` 는 권장 목표치(180)를 초과한다. 단, spec §7 이 **강제 AC 아님**
으로 명시하고 있어 phase 7 는 성공 처리한다. 추가 슬림화는 후속 라운드 과제.

## 7. 최종 판정

- 자동 검증 가능한 모든 항목 PASS.
- 수동 검증이 필요한 항목은 본 보고서에 **"수동 검증 대기"** 로 명시.
- 회귀 발견 0건. 코드 변경 없음.
