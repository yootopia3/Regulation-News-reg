# System Architecture (As-Built)

**Version**: 1.0.0
**Context**: MarketPulse-Reg (Regulatory News Analysis)
**Status**: Round 6-8 hardening complete

## 1. High-Level Architecture

2026-09-10 사용자 UI 변경: 제재/경영유의 카드의 기존 `AI 심층 보고서` 버튼이
`SanctionReportModal`을 연다. 게시 API를 기사 UUID로 조회해 요약 브리핑과
당행 부서·업무·점검 포인트를 보여준다. 일반 기사는 기존 생성 모달을 유지한다.
별도 제재 Report 하위 메뉴는 제거했고 과거 `/reports/sanctions` 직접 URL은 호환용으로 유지한다.
사용자가 확인한 운영 주소는 `https://regulation-news-reg-fiu7.vercel.app/`이다.

초기 Report 진입점 구현(아래 내용은 이전 진입점, 현재 주 경로는 카드 모달): Sidebar의 `Report → 재제공시 리포트`는
`/reports/sanctions`로 연결한다. 기존 인증된 `/api/articles`의 공개 공시 필드만
`web/lib/sanction-report.ts`에서 변환하고 `useSanctionSources`가 조회 상태를 관리한다.
이 화면은 최신 공시 최대 1,000건 조회·검색·원문 열기를 제공한다.
내부 문서 API를 호출하지 않으며 Stage B/C의 AI 부서 매칭·검토 게시 결과는 아직 연결하지 않았다.

The system follows a **Serverless Event-Driven** pattern using GitHub Actions as the primary execution environment.

```mermaid
graph TD
    Trigger[External Cron · cron-job.org] -->|workflow_dispatch| GHA[news_collector_v2_active.yml]
    GHA --> Main[src/main.py]
    Main --> Pipeline[src/pipeline.py]
    
    subgraph Data Collection
        Pipeline -->|Fetch| Scraper[src/collectors/scraper.py]
        Pipeline -->|Fetch| RSS[src/collectors/rss_parser.py]
    end
    
    subgraph Analysis Layer
        Pipeline -->|Raw Text| Analyzer[src/services/analyzer/*]
        Analyzer -->|Gemini 2.5| Tier1[Gatekeeper]
        Analyzer -->|Gemini 3.0| Tier2[Analyst]
        Analyzer -->|Keywords| Safeguard[Safeguard Rules]
    end
    
    subgraph Persistence & Alert
        Pipeline -->|Insert| Supabase[src/db/client.py]
        Pipeline -->|Notify| Telegram[src/services/notifier.py]
    end
```

---

## 2. Directory Structure (File Map)
This map reflects the **actual** codebase after round 1 refactor.

```
reg_brief/
├── .github/
│   └── workflows/
│       └── news_collector_v2_active.yml  # Production collector (triggered by external cron-job.org via workflow_dispatch)
├── config/
│   ├── agencies.json           # Target Agency Config (single source of truth)
│   └── safeguard_keywords.json # Keyword Override Rules
├── docs/                       # Documentation Assets
├── db/
│   └── schema.sql              # v1 schema snapshot (see Schema status below)
├── scripts/
│   └── v2_schema_setup.sql     # v2 schema snapshot (see Schema status below)
├── src/
│   ├── collectors/
│   │   ├── http.py             # HTTP fetch helpers
│   │   ├── date_parser.py      # Date normalization
│   │   ├── pagination.py       # Pagination helpers
│   │   ├── list_scraper.py     # List page scraping
│   │   ├── content_scraper.py  # Detail page scraping
│   │   ├── sanction_scraper.py # FSS sanction scraping
│   │   ├── rss_parser.py       # RSS parsing
│   │   └── scraper.py          # Facade
│   ├── config/
│   │   ├── settings.py         # Constants + env loading (Gemini model IDs via env)
│   │   ├── agency_codes.py     # Agency code constants (enum)
│   │   └── agency_loader.py    # Runtime-derived agency metadata (sanction codes)
│   ├── db/
│   │   └── client.py           # Supabase Connection
│   ├── services/
│   │   ├── analyzer/           # Hybrid analyzer package (see 4.1)
│   │   │   ├── hybrid.py
│   │   │   ├── prompts.py
│   │   │   ├── gemini_client.py
│   │   │   ├── result_mapper.py
│   │   │   └── safeguards.py
│   │   └── notifier.py         # Telegram Bot Logic
│   ├── utils/
│   │   ├── logger.py           # Centralized Logging
│   │   └── preserve.py         # analysis_result 키 보존 헬퍼 (admin/backfill 스크립트용)
│   ├── main.py                 # [Entry Point] Production Runner
│   └── pipeline.py             # [Core] Orchestration Logic
└── web/                        # Frontend (Next.js)
    ├── app/
    │   ├── page.tsx            # Live entry → DashboardV2
    │   ├── login/              # Login page
    │   └── api/
    │       ├── auth/login/     # Passcode → mp_session cookie
    │       └── report/         # Report endpoint (auth-guarded)
    ├── components/
    │   └── dashboard/
    │       ├── DashboardV2.tsx       # Live entry. round6-8에서 Sidebar/AgencyIcon/constants/useHasNewByCategory 등으로 분해됨
    │       └── ...                   # Header, NewsCard, SearchBar, StarRating, DateSection 등 기존 컴포넌트 유지
    ├── lib/
    │   ├── auth.ts             # HMAC session cookie helpers
    │   ├── prompts/report.ts   # buildReportPrompt() — report prompt template
    │   └── validation/report.ts # /api/report request schema
    ├── __tests__/              # vitest suites (api + lib)
    └── proxy.ts                # Route protection (mp_session cookie guards /api/*)
```

Tests live in `tests/unit/**` (pytest) and `web/__tests__/**` (vitest); both
are executed on PRs by `.github/workflows/ci.yml` (`python-test`,
`web-test`, `gitleaks` jobs).

The configured agency count is the length of the `agencies` array in
`config/agencies.json` (single source of truth).

---

## 3. Data Flow (Pipeline)
1.  **Collection**: `main.py` triggers `pipeline.run()`. Scrapers fetch data from agencies.
2.  **Deduplication**: `pipeline._is_duplicate()` checks `link` against DB.
3.  **Processing**:
    - **Step 1**: Tier 1 filter (Gemini 2.5) -> Score 0-5.
    - **Step 2**: Keyword safeguards -> Force Score 4/5 if keyword matches.
    - **Step 3**: Tier 2 analysis (Gemini 3.0) -> Runs only if Score >= threshold.
4.  **Storage**: `pipeline._save_item()` inserts JSON payload to Supabase.
    `pdf_url`이 있는 항목(주로 sanction)은 insert 직전에 `analysis_result` JSON 안으로 merge되어 단일 컬럼에 저장된다.
5.  **Alerting**: `notifier.format_and_send()` sends Telegram msg ONLY if `analysis_result` exists.

## 4. Key Components Detail

### 4.1 Hybrid Analyzer (`src/services/analyzer/`)
After round 1 refactor, the analyzer is a package, not a single file. Each
module owns a single responsibility; refer to the source for current
signatures.

- `hybrid.py` — orchestrates the 2-Tier + Safeguard strategy.
- `prompts.py` — prompt templates for Tier 1/Tier 2.
- `gemini_client.py` — Gemini API client wrapper. round5에서 `google-genai` SDK 기반으로 마이그레이션. 회귀 테스트는 `tests/unit/analyzer/test_gemini_client.py`.
- `result_mapper.py` — maps raw model output to internal result shape.
- `safeguards.py` — keyword-based score override rules.

Backend Gemini model IDs are env-driven via `src/config/settings.py`:
`GEMINI_FILTER_MODEL` (Tier 1), `GEMINI_ANALYZER_MODEL` (Tier 2), and
`GEMINI_ANALYZER_FALLBACK_MODEL` (Tier 2 fallback). Defaults live in
`settings.py`. The frontend `/api/report` route uses a separate
`GEMINI_REPORT_MODEL` env (default in `web/app/api/report/route.ts`).
Gemini calls are fail-closed behind `GEMINI_ENABLED`: unless the value is
explicitly set to `true`/`1`/`yes`/`on`, backend analysis and the web
`/api/report` route do not create Gemini SDK clients even when
`GEMINI_API_KEY` is present.

### 4.1.1 Sanction agency derivation
`SANCTION_AGENCY_CODES` is no longer a hardcoded frozenset. It is derived
at runtime by `src/config/agency_loader.get_sanction_codes()` from the
`category` field of `config/agencies.json` (entries with
`category == "sanction_notice"`). Adding a new sanction source therefore
requires only a JSON edit. 동일 모듈의 `get_ssl_verify(code)`도 같은 패턴으로
per-agency TLS verify 정책을 단일 진실원(`config/agencies.json`)에서 도출한다.

### 4.1.2 SSL verification policy
- 기본값: `src/config/settings.py`의 `SSL_VERIFY = True` (round6에서 `False`→`True`로 반전).
- per-agency opt-out: `config/agencies.json`의 `ssl_verify: false` 필드.
- 적용: `src/collectors/sanction_scraper.py`가 `agency_loader.get_ssl_verify(code)`로
  값을 읽어 `http.fetch(url, verify=...)`에 전달.
- 검증: `.github/workflows/ssl-matrix-check.yml`이 verify on/off 매트릭스로 회귀를 점검.

### 4.2 Supabase Client (`src/db/client.py`)
- **Responsibility**: Singleton connection to PostgreSQL.
- **Connection Logic**:
    - Backend collectors use `SUPABASE_URL`.
    - Write-capable backend paths prefer `SUPABASE_SERVICE_ROLE_KEY`.
    - If `SUPABASE_SERVICE_ROLE_KEY` is absent, the client falls back to `SUPABASE_ANON_KEY` for local/development compatibility. Hardened production RLS does not allow anon writes.
    - Frontend dashboard clients use the `NEXT_PUBLIC_*` Supabase URL/key pair through `web/utils/supabase/client.ts`.

### 4.3 Environment Configuration (Secrets Map)
*Updated for v2.0 Dual-Environment Setup*

| Variable Name | Purpose | Target (Where to Set) |
|---------------|---------|-----------------------|
| `NEXT_PUBLIC_SUPABASE_URL_V2` | v2 DB Endpoint | **Github Secrets** (Actions), **Vercel** (Preview) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY_V2` | v2 DB API Key | **Github Secrets** (Actions), **Vercel** (Preview) |
| `SUPABASE_SERVICE_ROLE_KEY_V2` | v2 service role key mapped to `SUPABASE_SERVICE_ROLE_KEY` in the collector workflow | **Github Secrets** (Actions) |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend/server write key used by Python collectors and `/api/report` | **Vercel** (Web), Local `.env`, mapped from `SUPABASE_SERVICE_ROLE_KEY_V2` in Actions |
| `NEXT_PUBLIC_USE_V2_DB` | v2 Switch Flag (`true`) | **Vercel** (Preview), Local `.env` |
| `ENV_TYPE` | Backend Branch Flag (`v2`) | **Github Actions** (`news_collector_v2.yml`) |
| `GEMINI_ENABLED` | Enables Gemini analysis/reporting only when explicitly true | **Github Actions**, **Vercel**, Local `.env` |
| `GEMINI_API_KEY` | Gemini API key, used only when `GEMINI_ENABLED` is true | **Github Actions**, **Vercel**, Local `.env` |
| `APP_PASSCODE` | Login passcode (server-side compare) | **Vercel** (Web), Local `.env` |
| `SESSION_SECRET` | HMAC key for `mp_session` cookie | **Vercel** (Web), Local `.env` |

### 4.4 Web Dashboard (`web/`)
- **Security**: Protected by `proxy.ts` (Cookie-based Auth). The
  `mp_session` cookie also gates all `/api/*` routes.
- **Visualization**: Reads directly from Supabase `articles` table.
- **`/api/report`**: Accepts only `{ articleId }` in the request body
  (schema in `web/lib/validation/report.ts`). The server then loads
  `title`, `content`, and `agency` from Supabase by id — clients cannot
  inject prompt content. The Gemini prompt is built by
  `buildReportPrompt()` in `web/lib/prompts/report.ts`, and the model id
  is taken from `GEMINI_REPORT_MODEL`. When `GEMINI_ENABLED` is not
  explicitly true, the route returns `503` before Supabase lookup or
  Gemini SDK construction.

### 4.5 Authentication
프론트엔드 인증은 서명된 `mp_session` HMAC 쿠키 기반이다. 사용자가 입력한
passcode는 `/api/auth/login` route 에서 서버측 `APP_PASSCODE` 환경변수와
비교되며, 일치하면 `SESSION_SECRET` 으로 서명된 세션 쿠키가 발급된다.
쿠키 발급/검증 로직은 `web/lib/auth.ts` 에 있고, 보호 대상 route는
`proxy.ts` 가 동일 헬퍼를 사용해 검사한다.

### 4.6 Schema status
현재 애플리케이션 코드와 `db/schema.sql` / `scripts/v2_schema_setup.sql`
사이에 불일치가 있을 수 있다. live DB 기준으로 검증한 뒤 적용하라.

### 4.7 Pipeline dependency injection (testability)
`Pipeline.__init__(config_path, *, analyzer=None, notifier=None, db=None, scraper=None)`.
None일 때 내부 헬퍼로 기본 구성하고, 단위 테스트는 fake를 주입해 외부 I/O 없이
오케스트레이션 흐름을 검증한다. 프로덕션 호출 경로(`src/main.py`)는 None만
넘기므로 동작이 동일하다.

### 4.8 Private document administration (Stage A; deployment pending)

`web/app/admin/` 및 `web/app/api/admin/`은 내부 HWP 관리 기능이다.
기존 passcode와 별도로 Supabase Auth 사용자와 서버 `ADMIN_USER_IDS`를 검증한다.
관리 API는 자체 권한 확인·Origin 검사·private 응답을 사용하며 일반 쿠키로 접근할 수 없다.
`INTERNAL_DOCUMENTS_ENABLED`의 명시적 true가 없으면 사용할 수 없다.

문서와 작업은 신규 비공개 테이블·Storage에 기록한다. 독립 실행 진입점
`python -m src.services.internal_documents.worker`가 작업을 claim하고
격리된 `parser` subprocess에서 HWP를 조문/업무로 추출한다. 일반 수집기와
Gemini 경로는 이 문서 데이터를 사용하지 않는다. 원문 검토·활성화 후의
제재 연결과 일반 결과 게시(Stage B/C)를 아래 별도 경로로 처리한다.
`src/services/sanction_inspections/`에 공개 페이지 텍스트와 선택 내부 조문을 분리해
Responses API로 처리하는 분석 라이브러리를 추가했다. 관리자 `/admin/inspections`와
`/api/admin/inspections`가 비공개 DB 큐에 연결되며 별도
`python -m src.services.sanction_inspections.worker`가 FSS PDF 다운로드·격리 추출·분석을 수행한다.
관리자 검토본 편집·게시·철회와 일반 사용자 게시 조회 및 XLSX 내보내기를 추가했다.
`/api/sanction-publications`는 서명된 일반 세션을 확인하고 별도 게시 테이블에서
허용된 DTO만 반환한다. 규정 변경·재분석 때 게시 snapshot도 무효화한다.
운영 배포는 미적용이다. 게시 설정은 `docs/sanction-inspection-publication.md`를 참고한다.
상세는 `docs/sanction-inspection-execution.md`를 참고한다.

운영 서비스 설정 및 검증은 `docs/internal-documents-setup.md`를 참고한다.
