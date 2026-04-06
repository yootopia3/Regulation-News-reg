# Backend Structure Refactor — Regression Report (Phase 7)

- Baseline commit: `8ef023a9d8b57530ce3b0dc51a19320495168d8a`
  (`docs: create backend-structure plan`, recorded in `baseline-commit.txt`)
- HEAD at verify time: `fabf2cd513a3127bcc42b9224f817ecb5298255f`

> **요약**: 자동 검증 완료 (PASS). 수동 회귀 검증 대기 (§4.2 참조).
> spec/refactor-round1.md §6.1 / §6.2 의 두 층 AC 구조에 맞춰 판정한다.

## 1. Acceptance Criteria

### 1.1 자동 검증 AC (spec §6.1) — runner / phase 7 판정

| # | AC | Result |
|---|---|---|
| A1 | `from src.pipeline import Pipeline` 사이드 이펙트 없이 통과 | **PASS** |
| A2 | `from src.services.analyzer import HybridAnalyzer` 사이드 이펙트 없이 통과 | **PASS** |
| A3 | agency 코드 문자열 리터럴 0건 (`src/pipeline.py`) | **PASS** — `grep -rEn "'(FSS_SANCTION\|FSS_MGMT_NOTICE)'" src/pipeline.py` 결과 0건 |
| A4 | DB 스키마 diff 0건 | **PASS** — 아래 통합 diff 명령에 포함 |
| A5 | `web/`, `config/agencies.json`, `.github/`, `scripts/`, `db/`, 루트 dump 파일 diff 0건 | **PASS** |
| A6 | 분석 결과 JSON 키 셋 동일 (코드 검토) | **PASS** — §5 참조 |

### 1.2 수동 회귀 검증 AC (spec §6.2) — 사용자가 `.env` 환경에서 수행

| # | AC | Result |
|---|---|---|
| M1 | `pip install -r requirements.txt` 성공 | **수동 검증 대기** (runner 실행 전 사전 수행 전제) |
| M2 | `python src/main.py` 1사이클 정상 종료, 9 agency 처리 로그 | **수동 검증 대기** — `.env` + 외부 서비스 필요 |
| M3 | 새 article 1건 이상 DB 저장 | **수동 검증 대기** — Supabase 연결 필요 |
| M4 | Telegram 알림 포맷 동일 | **수동 검증 대기** — 실제 알림 수신 확인 필요 |
| M5 | 제재 중복 체크가 동일 `examMgmtNo`+`emOpenSeq` 필터링 | **코드 검토 PASS** (§4 M5) + **수동 검증 대기** (실제 제재 아이템 기준) |

### 1.3 Out-of-scope 통합 diff 검증 (A4 + A5 근거)

```
BASELINE=$(cat tasks/1-backend-structure/baseline-commit.txt)
git diff --stat "$BASELINE" -- \
  web/ config/agencies.json .github/ scripts/ db/ \
  ./debug_*.md ./debug_*.py ./*.txt ./agency_stats.json
# (empty output — 변경 0건)
```

baseline = `8ef023a9d8b57530ce3b0dc51a19320495168d8a`. 위 명령의 출력이 비어 있어
루트 dump 파일(`debug_*.md`, `debug_*.py`, `*.txt`, `agency_stats.json`)을 포함한
모든 out-of-scope 경로의 diff 가 0 임을 확인.

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
  - `genai.configure(...)` 는 import 경로에서 호출되지 않음. `hybrid.py` 는
    `GeminiClient` 를 `HybridAnalyzer.__init__` 시점에 생성하고, `configure`
    호출은 `GeminiClient.__init__` 안에서만 일어난다 — 단순 import 로는 실행되지
    않는다.
  - `logging.basicConfig(...)` 는 `src/` 전체에 **존재하지 않는다**
    (`grep -rn "basicConfig" src/` 결과 0건). 로거 초기화는 `src/utils/logger.py`
    의 `setup_logger()` 가 담당하며, `src/main.py` 가 이를 호출한다. 이 호출은
    `main.py` 모듈 top-level 에 있지만 **pipeline/analyzer import 경로에는 포함
    되지 않기 때문에** `from src.pipeline import Pipeline` / `from
    src.services.analyzer import HybridAnalyzer` 단독으로는 트리거되지 않는다.

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

### 4.1 자동 검증 가능 항목

| # | 항목 | 결과 |
|---|---|---|
| A2 | `from src.pipeline import Pipeline` 사이드 이펙트 없이 통과 | **PASS** |
| A3 | `from src.services.analyzer import HybridAnalyzer` import 시 `genai.configure` / `logging.basicConfig` 호출 안 됨 | **PASS** — `hybrid.py` 는 `GeminiClient` 를 `HybridAnalyzer.__init__` 시점에 생성하여 `configure` 호출을 import 경로 밖으로 이동. `logging.basicConfig` 는 `src/` 전체에 아예 존재하지 않음 (`grep` 0건). 로거 설정은 `src/utils/logger.py::setup_logger()` 가 전담하며 `src/main.py` 가 호출한다. |
| M5-code | 제재 중복 체크가 동일 `examMgmtNo`+`emOpenSeq` 필터링 (코드 검토) | **PASS** — `src/pipeline.py` 의 `_is_duplicate` 가 `SANCTION_AGENCY_CODES` 분기 후 `extract_sanction_key(link)` 로 `(agency, examMgmtNo, emOpenSeq)` 튜플을 생성하여 `sanction_keys` 세트에 대해 검사. 링크 단위 fallback 도 유지. |
| A6-tg | Telegram 메시지 포맷 동일 (코드 검토) | **PASS** — pipeline 은 `notifier.format_and_send(agency, title, link, analysis_result)` 서명만 사용하며 notifier 모듈은 이번 라운드에서 변경 없음. |
| A6-json | 분석 결과 JSON 키 셋 동일 (코드 검토) | **PASS** — §5 참조 |

### 4.2 수동 검증 대기 항목

| # | 항목 | 검증 수단 |
|---|---|---|
| M1 | `pip install -r requirements.txt` 통과 | 환경 외부 — 사용자가 수행 |
| M2 | `python src/main.py` 1사이클 정상 종료, 9 agency 처리 | `.env` 필요 — runner 환경에서 실행 불가 |
| M3 | 새 article 1건 이상 DB 저장 | `.env` + Supabase 연결 필요 |
| M4 | Telegram 알림 포맷이 실제 알림에서도 동일 | `.env` + Telegram 토큰 필요 |
| M5-live | 실제 제재 아이템 기준 중복 체크 동작 확인 | 실데이터 필요 |

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

- **자동 검증 완료 (spec §6.1 전부 PASS).** runner/phase 7 기준으로 이번 라운드
  는 성공으로 본다. `tasks/1-backend-structure/index.json` 및 `tasks/index.json`
  의 task status `completed` 는 이 자동 검증 층에 대한 판정이다.
- **수동 회귀 검증 대기 (spec §6.2).** §1.2 / §4.2 의 M1~M5 항목은 `.env` + 외부
  서비스가 필요하므로 사용자가 별도로 수행한다. 이 항목들이 모두 해소되어야
  "라운드 1 종결" 로 본다.
- 자동 검증 범위 내에서 회귀 발견 0건. Phase 7 이 `src/` 코드를 수정하지 않았음
  (본 보고서와 `baseline-commit.txt` 추가, `tasks/1-backend-structure/index.json`
  status 갱신만 수행).

## 8. Round 2 Backlog — pipeline slim 후속 과제

`src/pipeline.py` 는 318 LOC 로 spec §7 권장 목표치(180)를 초과한다. 이번
라운드는 성공이지만 pipeline slim 은 후속 라운드 과제로 남긴다. 후보:

- collection planning 분리 (agency 선택 + cutoff/페이지 정책)
- per-item processing service 분리 (fetch → analyze → persist 파이프)
- persistence / notification 분리 (저장과 알림을 별도 sink 로)
