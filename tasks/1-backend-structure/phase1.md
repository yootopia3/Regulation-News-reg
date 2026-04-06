# Phase 1: Design Doc + Baseline Capture

이번 phase는 코드 변경 없음. 다음 phase들이 따라갈 모듈 경계 설계 문서를
`spec/backend-architecture.md`에 1장 작성하고, phase 7 회귀 검증용 baseline
commit hash를 기록한다.

## 사전 준비

먼저 라운드 전체 컨텍스트를 읽어라:

- `spec/refactor-round1.md` — 이번 라운드의 목적, scope, AC, 회귀 체크리스트
- `CLAUDE.md` — 프로젝트 규칙 (문자열 리터럴 금지, 네이밍 일관성, View/UI 비즈니스 로직 금지 등)

그리고 이번 task에서 손볼 핵심 소스를 직접 읽어라. source-first다:

- `src/main.py`
- `src/pipeline.py`
- `src/scheduler.py`
- `src/collectors/rss_parser.py`
- `src/collectors/scraper.py`
- `src/services/analyzer.py`
- `src/services/notifier.py`
- `src/db/client.py`
- `src/utils/logger.py`
- `config/settings.py`
- `config/agencies.json`
- `config/safeguard_keywords.json`

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰한다.

## 작업 내용

`spec/backend-architecture.md` 1장을 작성한다. 아래 섹션을 모두 포함하라:

1. **현재 구조 한눈에** — 디렉토리 트리 + 파일별 라인 수 + 각 파일이 가진 책임
   bullet (사실 위주, 평가 금지).
2. **목표 모듈 경계** — 라운드 1 이후의 디렉토리/파일 트리. 각 파일의 단일
   책임을 한 줄로 명시. 최소한 다음 분해 결과를 포함:
   - `src/config/` — `settings.py`(상수+env 로더), `agency_codes.py`(enum/상수)
   - `src/db/client.py` — lazy init
   - `src/services/analyzer/` — `__init__.py`(HybridAnalyzer 슬림), `prompts.py`,
     `gemini_client.py`, `safeguards.py`, `result_mapper.py`
   - `src/collectors/` — `http.py`(Session+headers), `date_parser.py`,
     `list_scraper.py`, `content_scraper.py`, `sanction_scraper.py`,
     `rss_parser.py`(기존 유지·정리)
   - `src/pipeline.py` — 슬림 오케스트레이터
3. **공개 인터페이스 표** — 외부에서 import하는 심볼이 phase 진행 후에도 동일하게
   유지되어야 함을 명시. 최소:
   - `src.pipeline.Pipeline`
   - `src.services.analyzer.HybridAnalyzer`
   - `src.services.analyzer.RegulationAnalyzer` (backward compat alias)
   - `src.services.notifier.TelegramNotifier`
   - `src.collectors.rss_parser.collect_all_rss`
   - `src.collectors.scraper.ContentScraper` (필요 시 facade로 유지)
   - `src.db.client.supabase` (lazy 객체로 유지)
4. **의존성 방향** — `pipeline → services/collectors/db → config → utils` 의
   단방향만 허용. 역방향 import 금지 명시.
5. **agency 코드 enum 계획** — 현재 코드에 박혀 있는 문자열 리터럴
   (`'FSS_SANCTION'`, `'FSS_MGMT_NOTICE'`, `'FSC'` 등) 위치를 grep으로 찾아 표로
   정리하고, `AgencyCode` enum/StrEnum 으로 어디서 어떻게 치환할지 적어라.
6. **side effect 제거 계획** — 현재 import 시점에 발생하는 사이드 이펙트 (`config
   /settings.py`의 모듈 import, `analyzer.py:30` `logging.basicConfig`,
   `analyzer.py`의 `genai.configure`, `db/client.py`의 raise) 위치를 모두 적고,
   각각을 어떻게 lazy 화할지 한 줄씩 적어라.
7. **이번 라운드에서 하지 않을 것** — `spec/refactor-round1.md` §3, §8을 그대로
   인용.

### 1.B Baseline commit hash 기록

phase 7이 out-of-scope 파일 diff를 비교할 기준점을 캡처한다. 작업을 시작하기
전 현재 HEAD 를 파일로 저장하라:

```bash
git rev-parse HEAD > tasks/1-backend-structure/baseline-commit.txt
```

이 파일은 `tasks/`에 들어가므로 사전 docs commit에 포함되어 후속 phase에서도
읽을 수 있다.

## Acceptance Criteria

```bash
test -f spec/backend-architecture.md
test -s spec/backend-architecture.md
grep -q "AgencyCode" spec/backend-architecture.md
grep -q "lazy" spec/backend-architecture.md
grep -q "side effect" spec/backend-architecture.md
test -s tasks/1-backend-structure/baseline-commit.txt
```

## AC 검증 방법

위 명령들을 직접 실행하라. 모두 성공하면 `tasks/1-backend-structure/index.json`의
phase 1 status를 `"completed"`로 변경하라.

3회 이상 시도해도 실패하면 status를 `"error"`로, 사유를 `error_message`에 기록하라.

## 주의사항

- 코드 변경 금지. 이번 phase는 문서만 작성한다.
- 새 디렉토리를 만들거나 기존 파일을 옮기지 마라. 다음 phase들이 한다.
- "과설계 금지". `spec/refactor-round1.md` §3에 명시된 out-of-scope 항목을 설계
  문서에 포함시키지 마라 (DB 스키마 변경, 프론트, MOEF 소스 교체, 잡파일 정리).
- 의견·평가는 최소화하고 사실 위주로 적어라.
- agency 코드 enum 표는 실제로 grep해서 위치(파일:라인)를 적어라. 추측 금지.
