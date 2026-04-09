# Refactor Round 6+ — Roadmap

작성일: 2026-04-08
작성 모드: 실행 계획 문서 (이 파일 → 후속 tasks/ 생성의 1:1 입력이 된다)
대상 범위: 이 라운드는 단일 task 로 수렴되지 않는다. 성격이 다른 3 축을 **task 단위로 쪼개서** 순차 진행할 것을 제안한다.

---

## 1. 목적

Round 1–5 를 거치며 구조·위생·프레임워크 업그레이드·SDK 이관은 정리되었다. 이번
라운드는 그 **다음 층** 을 다룬다:

1. **안전성(P0)**: 현재 `src/config/settings.py` 의 `SSL_VERIFY = False` 전역 기본값,
   `sanction_scraper` 가 수집한 `pdf_url` 이 저장 경로에서 **조용히 폐기** 되는 데이터
   손실, 그리고 `DashboardV2.tsx` 내부에 **렌더마다 재마운트** 되는 nested function
   component 같은 "지금 돌아가지만 언제 터져도 이상하지 않은" 흠 세 가지를 잡는다.
2. **구조(P1)**: `DashboardV2.tsx` 592 LOC 의 god component 분해, `Pipeline` 의
   testability (생성자 DI), 최소 통합 테스트 보강.
3. **위생(P2)**: deprecated 상수 제거 가능성, lazy import / magic number 주석화 /
   pre-commit 확장, `/api/report` rate limit 은 **별도 task 후보** 로 평가.

스코프 단위는 "round 6 하나의 거대 task" 가 아니라 **세 개의 작은 task** 로 분할
한다 (§9 참조). 이유: (a) 블라스트 반경이 백엔드 / 프론트엔드 / housekeeping 으로
확연히 갈리고, (b) 각 task 마다 회귀 위험도와 검증 커맨드가 다르며, (c) 사용자가
중간에 실행 여부를 결정할 수 있어야 하기 때문이다.

---

## 2. 현재 동작 (변하면 안 되는 것)

리팩토링이므로 "원래 이렇게 동작하던 것" 은 그대로 유지해야 한다. 특히:

- 실행 흐름: `cron-job.org → GH Actions(news_collector_v2_active.yml) →
  python src/main.py` — 트리거 메커니즘 변경 금지.
- 수집 agency: 9개 (`MOEF`, `FSC`, `FSS`, `BOK`, `FSC_REG`, `FSS_REG`,
  `FSS_REG_INFO`, `FSS_SANCTION`, `FSS_MGMT_NOTICE`). `config/agencies.json` 의
  URL/selector/필터 키워드 데이터 변경 금지.
- 수집 경로: RSS 2종 (`MOEF`, `FSC`), HTML list scraper 5종, sanction scraper 2종.
- dedup: 일반 `link` 기반 + 제재 `(agency, examMgmtNo, emOpenSeq)` 기반 두 축.
  dedup 의미론을 바꾸지 않는다.
- 분석 2-tier: `GeminiClient` (google-genai SDK) → filter → analyze, fallback model
  포함. 프롬프트 문자열 변경 금지. 응답 키셋 변경 금지.
- DB `articles` 스키마: 이번 라운드도 **컬럼 추가/삭제 0건**. `pdf_url` 은 신규 컬럼
  으로 만들지 않고 `analysis_result` JSON 안에 넣는 방향을 권장 (§12 논의 포인트 1).
- Telegram 알림 포맷 / 조건 (`analysis_status == 'ANALYZED'` 일 때만).
- 인증: `/login` → HMAC `mp_session` 쿠키 → `web/proxy.ts` gate. 쿠키 이름·서명
  알고리즘·401 JSON·redirect 경로 변경 금지.
- `/api/report` 계약: POST `{ articleId }` → 캐시 hit 시 저장된 report, miss 시
  Gemini 호출 후 `analysis_result.detailed_report` 캐시. 응답 스키마 고정.
- DashboardV2 의 **시각적 결과물**: 메뉴 열림/닫힘, NEW 뱃지 동작, 검색, 날짜/리스트
  토글, 리포트 모달 모두 기존과 동일. 분해 후에도 스크린샷 레벨에서 동일해야 한다.

---

## 3. 이번 라운드에서 해결할 문제

### 3.1 Confirmed (source-first 로 검증 완료)

- **C1. `SSL_VERIFY = False` 전역 기본값**
  - `src/config/settings.py:78` 에 `SSL_VERIFY = False` 로 박혀 있다.
  - `src/collectors/http.py:52` 의 공용 `fetch()` 가 그 값을 그대로 `requests.get(..., verify=settings.SSL_VERIFY)` 로 흘려 보낸다.
  - 즉 **list scraper / content scraper / sanction scraper 전체가 기본으로 SSL 검증 off** 상태다.
  - 단, `rss_parser.py:76` 는 `http.fetch` 를 경유하지 않고 `requests.get(target_url, ...)` 직접 호출이므로 RSS 경로는 영향 받지 않는다 (= 이미 verify=True).
  - 위험: 공용 유틸이 조용히 insecure default 를 쓰는 구조라, 새 agency 하나가 추가될 때마다 "MITM 에 무방비" 인 상태로 자동 포함된다.

- **C2. `pdf_url` 이 저장 경로에서 누락**
  - `src/collectors/sanction_scraper.py:147,150,158` — `pdf_url` 을 만들고 item dict 에 넣는다.
  - `src/pipeline.py:258–266` `_save_item` payload — `agency / title / link / published_at / content / analysis_result / category` 만 저장한다. **`pdf_url` 은 빠져 있다.**
  - 그 외 `pdf_url` consumer: 0개 (`grep pdf_url` 결과는 scraper 와 round1 task 문서뿐).
  - 결론: 제재 스크래퍼가 PDF 링크를 뽑아내는 비용을 들이지만 그 결과는 **어떤 경로로도 사용되지 않고 drop** 된다.
  - 참고: DB `articles` 테이블에 `pdf_url` 컬럼이 없다. 저장하려면 컬럼 추가 or `analysis_result.pdf_url` 에 embed. 컬럼 추가는 이 라운드의 "DB 스키마 변경 0건" 원칙에 저촉. → `analysis_result` embed 를 권장 (§12 논의 포인트 1).

- **C3. `DashboardV2.tsx` 내부 `Sidebar` nested function component**
  - `web/components/dashboard/DashboardV2.tsx:212` — `const Sidebar = () => ( ... )` 가 부모 render 함수 안에 **closure 로 정의** 되어 있다. 총 260+ 라인의 sidebar 가 전부 여기에 들어 있다.
  - DashboardV2 total: **592 LOC**. nested Sidebar 는 부모 state/handler 20+ 개를 close-over 한다 (isMenuOpen, isAgencyExpanded, isRegExpanded, isSanctionExpanded, isFSSRegGroupExpanded, selectedAgency, currentCategory, hasNewPress/Reg/Sanction, setCurrent... 등).
  - 위험: parent re-render 시마다 `Sidebar` 가 **새 함수 reference** 가 된다. React 는 이걸 새 컴포넌트 타입으로 보고 `<aside>` 를 통째로 언마운트 → 재마운트 한다. mount 시 애니메이션 / focus / scroll position / mobile 의 slide-in 트랜지션이 파손될 수 있고 퍼포먼스 페널티도 생긴다.
  - 부가 확인:
    - 상수 (`pressAgencies`, `regulationAgencies`, `sanctionAgencies`, `agencyNames`, `regAgencyNames`, `sanctionAgencyNames`, `agencyIcons`) 전부 컴포넌트 본체 안에 인라인 (line 15–208).
    - NEW 뱃지 계산 (`hasNewPress`, `hasNewReg`, `hasNewSanction`) 이 3번 반복된 동일 패턴 (line 37–56).
    - `import { ..., countNewArticles }` (line 7) — `countNewArticles` 는 import 만 하고 **사용하지 않음**. 죽은 import.
    - `article={selectedArticle as any}` (line 587) — ReportModal 에 `any` 캐스트로 타입 우회.

- **C4. 백엔드 테스트 커버리지 구멍**
  - `tests/unit/` 현황: `analyzer/` (gemini_client, result_mapper, safeguards), `collectors/` (date_parser, pagination, sanction_scraper), `config/` (agency_loader, settings_env), `pipeline/` (is_duplicate).
  - 구멍:
    - `tests/unit/collectors/test_rss_parser.py` **없음**. Round 2 에서 MOEF stale 경고를 붙였지만 이걸 검증하는 테스트가 없다. 3-attempt retry 정책도 테스트 없음.
    - `tests/unit/pipeline/` 에는 `test_is_duplicate.py` 뿐. **`Pipeline.run()` 레벨 테스트 없음**, `_save_item` / `_analyze_item` / `_notify_item` 의 조합 검증 없음.
  - `web/__tests__/api/report.test.ts` 만 프론트 쪽 존재. Dashboard / auth / proxy 렌더·동작 테스트 **없음**.

- **C5. Pipeline 의 DI-불친화 구조**
  - `src/pipeline.py:42–64` `_init_analyzer / _init_notifier / _init_db` 가 모두 **생성자 내부에서 try/except import** 로 의존성 생성. 테스트에서 mock 주입 포인트가 없다.
  - `Pipeline(config_path)` 시그니처에 이미 `config_path` 하나만 받게 되어 있고, 실제 의존성 주입 레이어가 없다.
  - 결과: `test_is_duplicate.py` 는 Pipeline 전체를 테스트하지 않고 `_is_duplicate` 하위 메서드만 뜯어서 테스트한다 — 왜냐하면 다른 길이 막혀 있기 때문.

- **C6. deprecated 상수 (MODEL_FILTER_ID / MODEL_ANALYZER_ID / MODEL_ANALYZER_FALLBACK)**
  - `src/config/settings.py:31–44` — 이미 "DEPRECATED. Do not rely on them in new code." 주석 있음. 러너 소비자는 `get_model_filter_id()` / `get_model_analyzer_id()` getter 를 쓴다.
  - 유일한 **남은 소비자**: `scripts/admin/reanalyze_articles.py:13` — `from config.settings import MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK`. 루트 `config/settings.py` 는 shim (`from src.config.settings import *`) 이므로 실제로는 `src.config.settings` 를 거친다.
  - 삭제 가능 여부: `scripts/admin/reanalyze_articles.py` 를 getter 로 갈아타게 하면 가능. 다만 `scripts/admin/**` 는 지난 라운드들에서 반복적으로 OOS 로 묶여 왔다 → §12 논의 포인트 4.

### 3.2 Partially confirmed

- **P1. pagination helper 중복 가능성**
  - `src/pipeline.py:69–140` `_load_existing_links` 와 `_load_sanction_keys` 가 둘 다 `range(start, start+page_size-1)` 루프 + `len(batch) < page_size` 종료 조건으로 동일한 pagination 패턴을 쓴다. 다만 후자는 agency 별 필터 (`.eq('agency', agency_code)`) 가 들어가 있고 key 변환 로직이 다르다.
  - 추출 가치: 있음, 단 작다. 10-20 LOC 줄이는 수준. 이번 라운드 필수 아님. 하려면 round 7 dashboard 분해와 묶지 말고 backend 안전성 task 에 옵션 phase 로 둘 것.

- **P2. DashboardV2 의 God-component 여부**
  - 592 LOC 는 "큰 컴포넌트" 가 맞지만, 단순히 라인 수만으로 god 라 부르긴 어렵다. 실제 책임 집약도가 문제:
    - 데이터 fetch (`fetchArticles`)
    - 필터 + 그룹핑 (`processedData`)
    - 카테고리/에이전시 state 관리
    - Sidebar 렌더링 (260+ 라인)
    - 뷰 토글
    - 리포트 모달 wiring
  - 6개 책임이 한 함수에 있다 → god component 판정. 다만 분해 위험도가 제일 높은 영역이라 phase 쪼갬을 강하게 해야 한다 (§10 Task 9 참고).

### 3.3 Not confirmed (이번 라운드에서 하지 말자)

- **N1. `/api/report` rate limiting**
  - 코드 읽어 본 결과 `web/app/api/report/route.ts` 는 입력 검증 + DB 조회 + Gemini 호출 + cache persist 의 완성도가 높다 (auth-hardening round 에서 한 번 다녔음). rate limit 이 없는 건 사실이지만, 이걸 붙이려면: (a) 저장소 결정 (Redis? Supabase table? Edge KV?), (b) 운영 영향 (false positive 시 사용자가 막힘), (c) 비용/스키마 논의. 리팩토링 라운드의 "동작 유지" 원칙과 상충 → **별도 micro-task** 로 분리 (§9 Task 10 의 "후보" 섹션).
- **N2. lazy import / agency loader caching / pre-commit 확장**
  - `agency_loader.py` 는 이미 `@lru_cache` 를 쓰고 있어 caching 이 필요 없다.
  - lazy import 는 round 1 에서 대부분 정리되었다 (`src/db/client.py` 의 `_LazySupabaseClient`, `http.py` 의 session 캐시 등). 지금 상태에서 추가로 바꿔서 얻을 구체적 이득이 없다.
  - pre-commit 은 이미 `.pre-commit-config.yaml` 존재 여부를 체크하지 않은 채로 주장하지 말 것. 본 라운드에서는 **확인 phase 없이 손대지 않는다**. 필요하면 후속 task 에서.
- **N3. magic number 주석화**
  - `sanction_scraper.py:21–22` `MAX_PAGES = 10` / `CUTOFF_DAYS = 30` 이 상수화는 되어 있지만 "왜 10 / 30 이냐" 의 근거 주석이 없다. 문서화는 가치가 있으나 동작 변경 0건 원칙에 부합하고, 분리하면 1 phase 가 "주석 추가" 로 끝난다. **task 10 hardening 의 묶음 중 1 꼭지** 로 흡수하는 수준.

---

## 4. 건드리지 않을 범위 (Out of scope)

- **DB 스키마**: 이번 라운드도 컬럼 추가/삭제 0건. `pdf_url` 은 `analysis_result` JSON 안 embed (§12 논의 포인트 1).
- **`config/agencies.json`** 의 URL/selector/키워드 데이터: 변경 금지. 단, **새 필드 추가** (예: `ssl_verify`) 는 허용한다 (스키마가 아닌 JSON 설정). 이 경우에도 기존 필드 값은 보존.
- **`.github/workflows/*`**: 기본 OOS. (round 3, 4 에서 actions 버전 업 완료.)
  단, **Round 6 Task 8 phase 2 의 SSL matrix 조사용 `.github/workflows/ssl-matrix-check.yml` 1 파일** 은
  명시적 예외 — `workflow_dispatch` 전용, `permissions: contents: read`,
  secrets / env 참조 금지, 다른 workflow 파일 수정 금지. 이 1 파일 외에는 변경 0건.
- **`scripts/admin/**`**: 기본 OOS. 두 가지 명시적 예외:
  1. Task 10 phase 1 (deprecated 상수 제거) 에서 `reanalyze_articles.py` 1 파일의 import 경로를 getter 로 교체.
  2. Task 8 phase 5 (pdf_url preserve) 에서 `reanalyze_articles.py` 1 파일이 `analysis_result` 를 덮어쓸 때 기존 `pdf_url` 을 carry 하도록 1 함수 호출 추가.
  그 외 파일 (특히 `run_backfill_safe.py`) 은 손대지 않는다 — §11 R6 참조.
- **Gemini 프롬프트 문자열**: 변경 금지.
- **Telegram 메시지 포맷**: 변경 금지.
- **`/api/report` 계약**: 입력 스키마 / 응답 스키마 / 캐시 키 변경 금지. rate limit 은 별도 task.
- **인증 스택**: `web/lib/auth.ts` signSession/verifySession 알고리즘, `web/proxy.ts` 매처, 쿠키 이름 불변.
- **Gemini SDK**: round 5 에서 이관 완료. 재이관 금지.
- **Scheduler 재도입**: round 3 에서 제거. 재도입 금지.

---

## 5. 검증 결과 요약

| 번호 | 리뷰 항목 | 상태 | 근거 파일:라인 |
| --- | --- | --- | --- |
| P0-1 | `SSL_VERIFY = False` 전역 기본값 | **Confirmed** | `src/config/settings.py:78` + `src/collectors/http.py:52` |
| P0-2 | `pdf_url` 이 저장 경로에서 누락 | **Confirmed** | `src/collectors/sanction_scraper.py:158` 생성, `src/pipeline.py:258–266` 저장 payload 에 없음 |
| P0-3 | `DashboardV2.tsx` 내부 Sidebar nested + god component | **Confirmed** | `web/components/dashboard/DashboardV2.tsx:212` nested closure, 592 LOC |
| P1-4a | 상수 분리 여지 | **Confirmed** | `DashboardV2.tsx:15–208` 전부 인라인 |
| P1-4b | Agency icon 분리 여지 | **Confirmed** | `DashboardV2.tsx:198–208` 10개 SVG 인라인 record |
| P1-4c | Sidebar 분리 여지 | **Confirmed** | C3 참고 |
| P1-4d | NEW 뱃지 계산 분리 여지 | **Confirmed** | `DashboardV2.tsx:37–56` 3회 반복 + `countNewArticles` 미사용 import |
| P1-4e | `as any` 캐스트 제거 여지 | **Confirmed** | `DashboardV2.tsx:587` |
| P1-5 | Pipeline testability (생성자 DI) | **Confirmed** | `src/pipeline.py:20–64`, 테스트는 `_is_duplicate` 만 |
| P1-6a | RSS retry/path test | **Confirmed (missing)** | `tests/unit/collectors/test_rss_parser.py` 없음 |
| P1-6b | scraper parsing smoke test | Partial | `test_sanction_scraper.py` 존재, 그러나 `list_scraper` / `content_scraper` 는 없음 |
| P1-6c | frontend render/auth/proxy smoke test | **Confirmed (missing)** | `web/__tests__/` 에 `api/report.test.ts` 1건 뿐 |
| P1-7 | deprecated 상수 제거 가능 여부 | **Confirmed (conditional)** | 유일 consumer = `scripts/admin/reanalyze_articles.py:13` |
| P2-8 | pagination helper 중복 | **Partially confirmed** | `src/pipeline.py:69–140`, 가치 small |
| P2-9a | lazy import 여지 | **Not confirmed** | 이미 round 1 에서 정리됨 |
| P2-9b | agency loader caching | **Not confirmed** | 이미 `@lru_cache` 적용 |
| P2-9c | pre-commit 확장 | **Not verified** | 본 라운드 scope 제외 |
| P2-9d | magic number 주석화 | **Partially confirmed** | `sanction_scraper.py:21–22` |
| P2-10 | `/api/report` rate limiting | **Not confirmed (deferred)** | 별도 task 후보 |

---

## 6. 우선순위

중요도 + 회귀위험 + 작업 의존성 세 축으로 재정렬한 결과:

**티어 A (즉시, 안전성 + 데이터 무결성):**
1. **C2 — `pdf_url` 데이터 손실 복구** (중요도↑, 회귀위험↓, 의존성↓). 사용되지 않는 필드를 저장 경로에 연결만 하면 된다. `analysis_result.pdf_url` embed 방식이면 스키마 변경 0건.
2. **C1 — SSL opt-in 전환** (중요도↑, 회귀위험↑↑, 의존성→ opt-out 리스트 검증 필요). 잘못 전환하면 FSS 등이 사이클 전체 실패할 수 있으므로 **per-agency opt-out 매트릭스를 먼저 조사/기록** 해야 한다. 코드 phase 앞에 조사 phase 필수.
3. **C5 — Pipeline DI 포인트 도입** (중요도↑, 회귀위험 mid, 의존성→ 후속 테스트의 전제조건). `Pipeline.__init__` 에 optional 의존성 주입 파라미터를 추가해 테스트 문을 연다. 실제 동작은 기존과 동일.
4. **C4 — 최소 통합 테스트 (pipeline run + rss_parser)** (중요도 mid, 회귀위험↓, 의존성← C5 에 의존). C5 없이는 pipeline run 테스트가 불가능.

**티어 B (구조 개선, 프론트 분해):**
5. **C3 + P1-4 — DashboardV2 분해** (중요도 mid, 회귀위험↑, 의존성↓ 백엔드와 독립). 5-6 phase 로 스몰 스텝. 각 phase 후 `npm run build && npm run test` 통과 필수.
6. **P1-6c — 프론트 render / auth / proxy smoke test** (중요도 mid, 회귀위험↓, 의존성← C3 분해 후). DashboardV2 가 쪼개진 뒤 건 render 테스트를 심는 편이 낫다.

**티어 C (housekeeping, 후순위):**
7. **C6 — deprecated 상수 제거** (중요도↓, 회귀위험↓, 의존성→ scripts/admin 정책 논의). 의사결정만 내리면 1 phase.
8. **P2 그룹 — magic number 주석 / lint 확장** (중요도↓, 회귀위험↓). 선택.
9. **N1 — `/api/report` rate limit** (중요도 mid, 회귀위험 mid, 의존성→ 저장소 결정). **별도 task 후보**, 이 라운드에 포함하지 않는다.

---

## 7. 권장 task 분할안

본 라운드는 "하나의 round6" 가 아니라 **task 3개** 로 나눈다. 사용자가 중간에 멈출
수 있어야 하고, 각 task 의 AC/build_command 가 크게 다르기 때문이다.

### 7.1 Task 8 — round6-backend-safety (tier A 전부)

- **왜 지금 해야 하는가**: `pdf_url` 누락 (C2) 은 이미 운영 중 데이터 손실이고,
  `SSL_VERIFY = False` (C1) 는 새 agency 가 붙을수록 기본값이 문제를 확산시킨다.
  Pipeline DI (C5) 와 통합 테스트 (C4) 는 이후 모든 백엔드 변경의 전제조건이다.
- **예상 영향 범위**: `src/config/settings.py`, `src/collectors/http.py`,
  `src/collectors/rss_parser.py`, `src/collectors/sanction_scraper.py`,
  `src/pipeline.py`, `config/agencies.json` (신규 선택 필드 `ssl_verify` 만),
  `tests/unit/pipeline/`, `tests/unit/collectors/test_rss_parser.py` (신설),
  `spec/round6/ssl-matrix.md` (신설).
- **선행 조건**: 없음. 이 라운드의 entry task.
- **자동 검증 가능 여부**: ✅ 전부. `python -c "from src.pipeline import Pipeline"`
  import smoke + `pytest tests/unit -q`. `.env` 불필요 (테스트는 mock).
- **commit_prefix / branch_prefix / push_on_complete**: `refactor` / `refactor` / `false`.
- **build_command**:
  `python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer" && python3 -m pytest tests/unit -q`

### 7.2 Task 9 — round7-dashboard-decomposition (tier B 전부)

- **왜 지금 해야 하는가**: DashboardV2 는 **single point of failure** 이다.
  FE 에서 뭘 고치려 해도 592 LOC / nested Sidebar 를 건드리게 된다. 분해는 후속
  FE 작업 (검색 UX 개선, NEW 로직 변경, 에이전시 추가) 의 전제조건.
- **예상 영향 범위**: `web/components/dashboard/DashboardV2.tsx`,
  `web/components/dashboard/Sidebar.tsx` (신설),
  `web/components/dashboard/AgencyIcon.tsx` (신설),
  `web/components/dashboard/constants.ts` (신설),
  `web/components/dashboard/useHasNewByCategory.ts` (신설),
  `web/__tests__/components/dashboard/` (신설),
  필요 시 `web/__tests__/lib/auth.test.ts`, `web/__tests__/proxy.test.ts` (phase 6 에서 검토).
- **선행 조건**: Task 8 완료 (백엔드 쪽이 조용해야 프론트 분해의 회귀를 잡기 쉽다).
  **단, 코드 종속성은 없다** — 병렬 작업 자체는 이론상 가능하나 사용자 검증 부담을
  줄이려면 순차 진행 권장.
- **자동 검증 가능 여부**: ✅ `cd web && npm run build && npm run test`. 시각적 회귀
  는 자동 검증 대상 아님 → 회귀 체크리스트에 **수동 항목** 으로 둔다 (§8).
- **commit_prefix / branch_prefix / push_on_complete**: `refactor` / `refactor` / `false`.
- **build_command**: `cd web && npm run build && npm run test`

### 7.3 Task 10 — round8-hardening (tier C 옵션, 사용자 승인 필수)

- **왜 지금 해야 하는가**: 다음 세 가지를 한 번에 털어내는 **청소 task**. 각 꼭지가
  너무 작아서 독립 task 로 두면 runner 오버헤드가 본체보다 커진다.
  1. Deprecated 상수 (`MODEL_FILTER_ID` 등) 제거 + `scripts/admin/reanalyze_articles.py`
     를 getter 로 갈아끼기.
  2. `sanction_scraper.py` 의 `MAX_PAGES=10` / `CUTOFF_DAYS=30` 근거 주석 추가.
  3. 필요 시 `web/__tests__/lib/auth.test.ts`, `web/__tests__/proxy.test.ts` 보강
     (Task 9 에서 커버하지 못한 경우).
- **예상 영향 범위**: `src/config/settings.py`, `scripts/admin/reanalyze_articles.py`,
  `src/collectors/sanction_scraper.py`, `tests/unit/config/test_settings_env.py`
  (deprecated 상수 테스트 정리), `web/__tests__/lib/`, `web/__tests__/`.
- **선행 조건**: Task 8, 9 완료.
- **자동 검증 가능 여부**: ✅ python pytest + web build/test.
- **`/api/report` rate limit 은 이 task 에 포함하지 않는다.** 포함 여부는 사용자가
  별도로 결정 (§12 논의 포인트 5).
- **commit_prefix / branch_prefix / push_on_complete**: `refactor` / `refactor` / `false`.
- **build_command**:
  `python3 -m pytest tests/unit -q && cd web && npm run build && npm run test`

### 7.4 분할 근거 (하나로 묶지 않는 이유)

- Task 8 은 **백엔드 전용**, Task 9 는 **프론트엔드 전용** 이라 build_command 가 다르고
  각 task 의 회귀 체크리스트가 완전히 분리된다. 묶으면 runner 의 per-phase build
  검증이 무거워지고, 한 축이 깨졌을 때 다른 축까지 블록된다.
- Task 8 의 phase 1 (SSL 조사) 은 의사결정이 필요하므로 중간에 사람이 들어올 수 있다.
  Task 9 의 phase 1 (상수 추출) 은 순수 기계적 추출이라 자동 runner 가 빠르게 돈다.
  두 성격을 섞으면 runner 경험이 불균질해진다.
- Task 10 은 "짧지만 결정이 필요한" 것들의 묶음이라 사용자 승인 단계가 하나 더
  필요하다. 이 결정 단계를 Task 8/9 와 섞으면 sequential 실행을 깰 위험이 있다.

---

## 8. Phase 초안

phase 파일 자체는 아직 작성하지 않는다. 여기에는 **각 task 의 phase 이름 + 핵심
의도 + AC 한 줄** 만 두어 후속 `prompts/task-create.md` 프로세스의 입력으로 쓴다.

### 8.1 Task 8 — round6-backend-safety (6 phases)

| # | phase-slug | 무엇을 | 핵심 AC |
| --- | --- | --- | --- |
| 1 | `ssl-matrix-investigation` | `spec/round6/ssl-matrix.md` 작성. 9개 agency 각각에 대해 `verify=True` 로 실제 HTTP HEAD/GET 을 시도해 어떤 도메인이 certificate chain 실패를 반환하는지 표로 기록. 코드 변경 0. | `spec/round6/ssl-matrix.md` 가 `agencies.json` 의 모든 code 를 다루며 각 항목에 `verify_true_ok`, `error_type`, `decision (default/opt-out)` 컬럼을 채운다. |
| 2 | `ssl-opt-in-implementation` | `src/config/settings.py` `SSL_VERIFY` 기본값 = `True` 로 전환. `src/collectors/http.py` `fetch()` 에 `verify: Optional[bool] = None` 파라미터 추가, None 이면 agency 설정 조회 → 없으면 `settings.SSL_VERIFY`. `config/agencies.json` 의 opt-out 대상 agency 에 `"ssl_verify": false` 필드 추가 (§8.1 phase 1 결과 기반). `rss_parser.py` 도 동일 결정 채널 경유. | `pytest tests/unit/collectors -q` 통과. `grep '"ssl_verify"' config/agencies.json` 의 결과가 phase 1 매트릭스와 일치. |
| 3 | `pdf-url-persistence` | `src/pipeline.py` `_save_item` 이 `analysis_result` 안에 `pdf_url` 필드를 embed 하도록 수정 (분석이 이미 끝난 뒤). 분석 결과 JSON 스키마에 `pdf_url` 이 optional 키로 추가됨을 `spec/` 에 1줄 기록. Telegram 알림 포맷은 변경 금지. | `pytest tests/unit/pipeline -q` 통과. `_save_item` 이 받은 item 에 `pdf_url` 이 있으면 payload 의 `analysis_result.pdf_url` 에 반영되는 단위 테스트가 신설되어 있다. |
| 4 | `pipeline-di-refactor` | `Pipeline.__init__` 시그니처를 `Pipeline(config_path, *, analyzer=None, notifier=None, db=None, scraper=None)` 로 확장. 기본값 None 일 때만 기존 try/except import 경로를 통해 생성. `src/main.py` 는 변경 없음 (기본 경로 유지). | `python -c "from src.pipeline import Pipeline; Pipeline('config/agencies.json')"` 가 기존과 동일하게 동작. |
| 5 | `pipeline-run-test` | `tests/unit/pipeline/test_run.py` 신설. 가짜 analyzer/notifier/db/scraper + 2-3 건의 fake item 을 구성해 `Pipeline.run()` 을 1사이클 실행하고 `save / notify` 호출 여부와 dedup 동작을 assert. | `pytest tests/unit/pipeline -q` 통과. `test_run.py` 가 최소 3 케이스 (중복 1건 / 신규 1건 / 분석 실패 1건) 를 덮는다. |
| 6 | `rss-parser-test` | `tests/unit/collectors/test_rss_parser.py` 신설. `parse_date`, `fetch_rss_feed` (mocked requests → 200/ConnectionError/Timeout), 3-attempt retry 소진, `RSS_STALE_WARN_DAYS` 경고 로그 출력 케이스를 덮는다. | `pytest tests/unit/collectors -q` 통과. stale 경고 케이스는 `caplog` 로 `"[STALE RSS]"` 부분 문자열을 확인. |

### 8.2 Task 9 — round7-dashboard-decomposition (6 phases)

| # | phase-slug | 무엇을 | 핵심 AC |
| --- | --- | --- | --- |
| 1 | `constants-extraction` | `web/components/dashboard/constants.ts` 신설. `pressAgencies`, `regulationAgencies`, `sanctionAgencies`, `agencyNames`, `regAgencyNames`, `sanctionAgencyNames`, 주문 배열 전부 이관. `DashboardV2.tsx` 는 `import { ... } from './constants'`. 동작 무변경. | `cd web && npm run build && npm run test` 통과 + `DashboardV2.tsx` 내 인라인 상수 0건 grep. |
| 2 | `agency-icon-component` | `web/components/dashboard/AgencyIcon.tsx` 신설. Props: `{ code: AgencyCode | string; className?: string }`. 10개 SVG 를 case 매칭. `DashboardV2.tsx` 의 `agencyIcons` record 삭제. | `npm run build && npm run test` 통과 + 수동 비주얼 regression check (§9 수동 항목). |
| 3 | `new-badge-hook` | `web/components/dashboard/useHasNewByCategory.ts` 신설. `(articles, lastVisitTime) => { hasNewPress, hasNewReg, hasNewSanction }`. `countNewArticles` import 제거 (죽은 코드). | `npm run build && npm run test` 통과 + `grep countNewArticles web/components/dashboard/DashboardV2.tsx` 결과 0건. |
| 4 | `sidebar-extraction` | `web/components/dashboard/Sidebar.tsx` 신설. nested closure 에서 시블링 컴포넌트로 승격. Props 로 `currentCategory`, `selectedAgency`, `isMenuOpen`, `onCloseMenu`, `onSelect(category, agency)`, `expansionState`, `onToggleExpansion`, `hasNewPress/Reg/Sanction` 을 받는다. `DashboardV2.tsx` 는 `<Sidebar {...props} />` 호출 1줄. | `npm run build && npm run test` 통과. `DashboardV2.tsx` LOC 가 592 → ≤ 300 이하로 감소. |
| 5 | `report-modal-type-fix` | `web/components/ReportModal` 의 `article` prop 타입을 실제 `Article` 타입으로 좁힘. `DashboardV2.tsx:587` 의 `as any` 제거. 타입 미스매치가 있으면 `Article` 정의 확장. | `npm run build` 통과 + `grep "as any" web/components/dashboard/DashboardV2.tsx` 결과 0건. |
| 6 | `dashboard-render-smoke-test` | `web/__tests__/components/dashboard/DashboardV2.test.tsx` 신설 (vitest + @testing-library/react + jsdom). 최소 케이스: mocked supabase 로 빈 articles → "검색 결과가 없습니다" 노출, 3건 주입 → Sidebar 버튼 클릭으로 카테고리 토글 시 currentCategory 변경. auth 관련 smoke 는 별도 `web/__tests__/proxy.test.ts` 로 (verifySession 만 호출하는 순수 유닛 레벨). | `npm run test` 통과, 신규 테스트 2개 파일 이상. |

### 8.3 Task 10 — round8-hardening (3 phases)

| # | phase-slug | 무엇을 | 핵심 AC |
| --- | --- | --- | --- |
| 1 | `deprecated-constants-removal` | `src/config/settings.py` 의 `MODEL_FILTER_ID` / `MODEL_ANALYZER_ID` / `MODEL_ANALYZER_FALLBACK` 상수 삭제. `scripts/admin/reanalyze_articles.py:13` 을 getter import 로 교체 (`from src.config.settings import get_model_analyzer_id, get_model_analyzer_fallback`). `tests/unit/config/test_settings_env.py` 의 legacy 검증 케이스를 getter 기반으로 다시 쓴다. | `pytest tests/unit/config -q` 통과. `grep '^MODEL_FILTER_ID' src/config/settings.py` 결과 0건. `python -c "from scripts.admin.reanalyze_articles import reanalyze_all"` import smoke 성공 (실행은 하지 않는다). |
| 2 | `magic-number-docstrings` | `src/collectors/sanction_scraper.py` `MAX_PAGES=10`, `CUTOFF_DAYS=30` 에 "왜 이 값인지" 1-2 줄 주석 추가. 값 자체는 변경 금지. | `pytest tests/unit/collectors -q` 통과 + `grep -n "MAX_PAGES\|CUTOFF_DAYS" src/collectors/sanction_scraper.py` 결과 맨 앞 2줄에 docstring 블록 존재. |
| 3 | `auth-proxy-tests` | `web/__tests__/lib/auth.test.ts` 신설: `signSession` → `verifySession` 라운드트립, `SESSION_SECRET` 미설정 시 throw/return null, 만료/변조 토큰 거부 케이스. `web/__tests__/proxy.test.ts` 신설: `/login`, `/api/auth/login`, `/api/` (unauth), `/` (unauth → redirect) 케이스. | `cd web && npm run test` 통과. 두 신규 테스트 파일 존재. |

---

## 9. 회귀 체크리스트

### 9.1 Task 8 (backend-safety) 완료 후

- [ ] `pytest tests/unit -q` 통과 (기존 + 신규 테스트 전부).
- [ ] `python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"` import smoke 통과.
- [ ] `python src/main.py` 1사이클 로컬 수동 실행 (사용자). 9개 agency 전부 처리.
- [ ] 제재 공시 1건 이상 신규 저장되고, `analysis_result.pdf_url` 필드가 채워져 있다.
- [ ] SSL 변경으로 **새로 실패하는** agency 가 없다 (phase 1 매트릭스에서 opt-out 결정된 것 제외).
- [ ] Telegram 알림이 기존과 동일 포맷으로 발송된다.
- [ ] 분석 결과 JSON 키 셋이 기존 + `pdf_url` 옵션 키 이외에는 동일.

### 9.2 Task 9 (dashboard-decomposition) 완료 후

- [ ] `cd web && npm run build && npm run test` 통과.
- [ ] 수동 확인 (브라우저): 홈 / 보도자료 / 규제개정 / 제재 공시 카테고리 토글 정상. NEW 뱃지 정상. 검색 정상. 날짜/리스트 토글 정상. 리포트 모달 open/close 정상.
- [ ] 모바일 사이즈에서 햄버거 → 사이드바 슬라이드인 애니메이션 정상. 백드롭 클릭 시 닫힘.
- [ ] FSS 하위 메뉴 2단 확장/접힘 정상.
- [ ] `grep -c "as any" web/components/dashboard/DashboardV2.tsx` 결과 0.
- [ ] `DashboardV2.tsx` 라인 수가 ≤ 300 으로 줄었다.

### 9.3 Task 10 (hardening) 완료 후

- [ ] `pytest tests/unit -q` 통과.
- [ ] `cd web && npm run test` 통과.
- [ ] `scripts/admin/reanalyze_articles.py` 가 여전히 **import 가능** 하다 (실제 실행은 하지 않는다).
- [ ] `grep '^MODEL_FILTER_ID\|^MODEL_ANALYZER_ID\|^MODEL_ANALYZER_FALLBACK' src/config/settings.py` 결과 0.

---

## 10. AC (전체 roadmap 완료 기준)

3개 task 의 AC 를 각각 별개로 평가한다. "roadmap 완료" 는 Task 8, 9 통과 시점으로
간주하며 Task 10 은 선택 적용.

### 10.1 자동 검증 AC

- Task 8: `pytest tests/unit -q` 통과 + pipeline import smoke 통과.
- Task 9: `cd web && npm run build && npm run test` 통과.
- Task 10: Task 8 + 9 AC 를 그대로 유지.

### 10.2 수동 회귀 검증 AC (사용자 `.env` 환경)

- Task 8: `python src/main.py` 1사이클 정상 종료 + 새 sanction 기사 1건 이상 저장 + `analysis_result.pdf_url` 존재 + Telegram 알림 포맷 동일.
- Task 9: 브라우저 수동 흐름 체크리스트 (§9.2) 전부 통과.

---

## 11. 리스크

- **R1. SSL opt-out 매트릭스의 재현성**
  - FSS/FSC/BOK 의 실제 TLS 서명 체인은 시점 / 네트워크 / CA 번들에 따라 다르게 실패할 수 있다. phase 1 조사는 **개발 환경 1회 스냅샷** 일 뿐이며, GH Actions runner 환경에서 다시 돌면 결과가 달라질 수 있음. 대응: phase 1 의 매트릭스에 "조사 시각 + 환경" 을 기록하고, phase 2 에서 opt-out 리스트에 포함된 각 agency 에 대해 **"실패 시 자동 fallback 하지 않는다"** (침묵 회귀 방지) 는 원칙을 명시.
- **R2. `pdf_url` 을 `analysis_result` 에 embed 할 때 재분석 경로의 충돌**
  - `scripts/admin/reanalyze_articles.py` 는 `analysis_result` 를 덮어쓴다. 만약 재분석이 `pdf_url` 을 보존하지 않으면 소실. 대응: Task 10 의 deprecated 상수 제거 phase 에서 **reanalyze 경로가 기존 `pdf_url` 을 preserve** 하도록 같이 손본다 (이건 Task 10 의 scope 가 커지는 쪽이므로 §12 논의 포인트 2).
- **R3. DashboardV2 분해 중 시각적 회귀**
  - 자동 테스트로는 픽셀 레벨 회귀를 잡지 못한다. 대응: phase 마다 `npm run build` 뿐 아니라 **개발자 수동 브라우저 체크** 를 회귀 체크리스트에 넣는다 (§9.2).
- **R4. `_is_duplicate` 테스트가 이미 존재하는 상태에서 pipeline DI 리팩토링 시 기존 테스트 깨짐**
  - 대응: phase 4 에서 기존 `test_is_duplicate.py` 가 `Pipeline(config_path)` 시그니처를 쓰지 않는지 먼저 확인. 사용한다면 phase 4 의 AC 에 "기존 테스트 그대로 통과" 를 명시.
- **R5. `scripts/admin/**` 를 건드리지 않는 역대 정책과 Task 10 phase 1 의 충돌**
  - 대응: §12 논의 포인트 4 로 사용자에게 결정권 넘김. 결정 전까지 Task 10 phase 1 은 착수하지 않는다.
- **R6. `scripts/admin/run_backfill_safe.py` 의 알려진 한계 (이번 라운드 OOS)**
  - 사실 1: line 269–272 가 `analysis_result` 를 직접 overwrite 한다 (`update({'analysis_result': analysis})`). sanction 경로에서 `pdf_url` 이 들어 있던 행에 backfill 을 돌리면 `pdf_url` 이 소실된다.
  - 사실 2: line 72 의 `requests.get(..., verify=False)` 가 `settings.SSL_VERIFY` 와 무관하게 하드코딩되어 있어, Task 8 phase 3 의 SSL opt-in 결과가 backfill 경로에는 적용되지 않는다.
  - 결정: 이번 라운드는 두 한계 모두 **OOS**. 이유:
    1. backfill 은 수동 운영 도구이고 빈도가 낮아 운영적 영향이 작다.
    2. preserve 적용에는 추가 SELECT (`analysis_result` 컬럼 fetch) + 분석 루프 구조 변경이 필요해, 최소 수정 원칙을 명백히 넘는다.
    3. 같은 phase 에 묶으면 phase 5 의 testability 가 무너진다 (`BackfillPipeline` 인스턴스를 fake 로 굴리기 어려움).
  - 별도 후속 micro-task 후보: "`run_backfill_safe.py` 의 SSL/pdf_url 정합성" 라운드. 다음 라운드 검토.

---

## 12. 논의 필요 사항 (사용자 승인 필요)

아래 5개는 phase 파일 작성 전에 사용자 결정을 받아야 한다.

### Q1. `pdf_url` 저장 위치

- **옵션 A (권장)**: `analysis_result` JSON 안에 `pdf_url` 키로 embed. DB 스키마 변경 0건. 기존 reader 는 무시하면 되고, 새 FE 가 원할 때만 읽는다.
- **옵션 B**: `articles` 테이블에 `pdf_url` 컬럼 추가. 깔끔하지만 **이번 라운드의 "DB 스키마 변경 0건" 원칙 위반** + 기존 INSERT 경로 전부 확인 필요.
- **옵션 C**: 저장하지 않고 Telegram 알림에만 포함. 사용자가 이미 알림을 본 이후에는 접근 불가.
- 내 추천: **A**. 스키마 안정성 원칙을 유지하면서 데이터 손실을 막는다. B 는 다음 성능/스키마 round 에서 같이 옮기는 편이 낫다.

### Q2. 재분석 경로 (`scripts/admin/reanalyze_articles.py`) 에서 `pdf_url` 보존

- 옵션 A 를 선택하면 재분석이 기존 `analysis_result` 를 덮어쓸 때 `pdf_url` 이 사라질 수 있다.
- **옵션 A-1 (권장)**: Task 8 phase 3 에서 "재분석 경로도 `pdf_url` 을 preserve" 하도록 함께 수정. scripts/admin 을 1 파일 건드린다.
- **옵션 A-2**: Task 10 phase 1 로 미룸. 그 사이 재분석을 돌리면 손실 가능.
- **옵션 A-3**: 재분석 금지 플래그를 문서화만 하고 코드 변경 없음.
- 내 추천: **A-1**. scripts/admin 을 단 1 파일, 그것도 이미 Task 10 에서 건드리는 파일에 한해 스코프 확장.

### Q3. SSL opt-in 조사 phase 의 실행 환경

- **옵션 A**: 로컬 dev 환경에서 1회 HEAD/GET 하여 매트릭스 생성.
- **옵션 B**: GH Actions runner 에 one-shot workflow 를 돌려 생성 (실제 운영 환경과 동일).
- **옵션 C**: 둘 다 돌려서 diff 를 비교. diff 가 있으면 "환경 의존" 임을 명기.
- 내 추천: **A 로 시작 → 차이가 나면 C**. B 부터 하면 runner 오염 위험 + 크레딧 소비.

### Q4. `scripts/admin/reanalyze_articles.py` 수정 허용 여부

- Task 10 phase 1 (deprecated 상수 제거) 와 Task 8 phase 3 (pdf_url preserve, Q2-A-1 선택 시) 은 둘 다 `scripts/admin/reanalyze_articles.py` 를 건드려야 한다.
- 과거 라운드 (round 1, 2, 3) 는 `scripts/admin/**` 을 OOS 로 못 박았다.
- **옵션 A (권장)**: `scripts/admin/reanalyze_articles.py` **1 파일에 한해** 이번 라운드 OOS 해제. 그 외 `scripts/admin/**` 는 계속 OOS.
- **옵션 B**: OOS 유지 → deprecated 상수 제거 불가 → Task 10 phase 1 삭제.
- 내 추천: **A**. 대상 파일 1 개라면 "스코프 크립" 이라 부르기 어렵고, 유일한 consumer 제거 없이는 deprecated 를 영구 보존해야 한다.

### Q5. `/api/report` rate limit 을 이번 roadmap 에 포함할지

- **옵션 A (권장)**: 포함하지 않는다. 별도 독립 micro-task 로 다룬다. 이유: 저장소 결정 / 운영 영향 / false positive 사용자 경험 등 **본질적으로 리팩토링이 아닌 기능 결정**.
- **옵션 B**: Task 10 phase 4 로 추가. 단 Supabase 테이블 1개 추가 필요.
- 내 추천: **A**. 이 roadmap 은 "코드 품질" 라운드라는 정체성을 유지하고, rate limit 은 별개로.

---

## 부록. 참고 스냅샷

- Task 진행 상황 (`tasks/index.json`): round 1–5 완료 (id 1–7). 다음 신규 task id 는 **8** 부터.
- Round 1 스타일 문서: `spec/refactor-round1.md`, `spec/backend-architecture.md`.
- Round 2 스타일 문서 (좁은 스코프): `spec/moef-source-round2.md`.
- 본 문서는 Round 1 스타일 (다축 롤업) 에 가까우나, **task 분할 결정** 이 포함되어
  있다는 점이 다르다.
