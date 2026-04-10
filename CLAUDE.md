# CLAUDE.md

`reg_brief` — 한국 금융 규제기관(FSC, FSS, MOEF 등)의 보도자료와 제재
공시를 수집·분석해 텔레그램과 웹 대시보드로 브리핑하는 시스템. 백엔드는
Python (Pipeline + Hybrid Analyzer + Supabase), 프론트엔드는 Next.js,
실행은 GitHub Actions + 외부 cron-job.org.

## 기능추가 작업 절차 (superpowers 기반)

기능추가는 superpowers 절차를 기본으로 따른다.

**full 절차가 필요한 경우:**
- 새 기능 추가
- 구조 변경 (디렉토리, 모듈 경계, 데이터 흐름)
- 외부 연동 추가 (API, DB 테이블, 서드파티)
- schema / API contract / 운영 동작에 영향이 있는 변경

→ brainstorming → writing-plans → executing-plans
→ verification-before-completion
→ requesting-code-review / receiving-code-review

주요 변경 완료 후 review lane은 별도 단계로 둔다. 작성 pass와 검토
pass를 같은 context에서 self-approve하지 않는다.

**축약 또는 직접 수정이 허용되는 경우:**
- 국소 버그 수정 (명백한 1-file fix)
- 사소한 문서 수정
- 이미 plan이 합의된 범위 안의 minor 조정

→ 수정 후 verification은 여전히 필수. evidence 없는 success 주장 금지.

작업 단위가 2개 이상의 독립 sub-project로 분해되면, 각각 별도
brainstorm → plan → execute 사이클로 돌린다.

작업 도중 새로운 함정/제약을 발견하면 "시행착오 일지" 섹션에 사용자
합의 후 추가한다.

## 문서 우선순위

정보가 충돌할 때의 우선순위. 위가 높다:

1. **코드** (실제 구현이 진실)
2. **`docs/ARCHITECTURE.md`** — as-built 구조 (round6-8 sync 완료)
3. **`docs/SCHEMA.md`** — DB 컬럼, JSONB shape, 인덱스
   **`docs/REQUIREMENTS.md`** — Gemini 모델, 수집 주기, 운영 제약
4. **`docs/PRD.md`** / **`docs/MASTER_CONTEXT.md`** — 제품 맥락·제약
   참고용. 구현 사실은 이 문서들보다 위 1-3이 우선.

**읽기 트리거** — 아래 영역을 건드리기 전에 해당 문서를 먼저 읽어라:

| 건드리는 영역 | 먼저 읽을 문서 |
|---|---|
| DB 컬럼 / JSONB shape / SQL / dedup 키 | `docs/SCHEMA.md` |
| Gemini 모델 / 수집 주기 / timezone / safeguard 규칙 | `docs/REQUIREMENTS.md` |
| 모듈 경계 / 데이터 흐름 / 인프라 | `docs/ARCHITECTURE.md` |
| 제품 방향 / 사용자 시나리오 / 비즈니스 제약 | `docs/PRD.md` |

## 프로젝트 지도

상세 as-built 구조는 `docs/ARCHITECTURE.md`를 본다.

최상위:
- `src/` — 백엔드 (collectors, services/analyzer, db, pipeline)
- `web/` — Next.js 프론트엔드 (dashboard + 인증된 API)
- `tests/` — pytest (`tests/unit/**`); `web/__tests__/**` — vitest
- `docs/` — ARCHITECTURE / PRD / SCHEMA / REQUIREMENTS / MASTER_CONTEXT
- `spec/` — 라운드별 refactor spec / 로드맵
- `scripts/` — admin / monitor / archive 유틸
- `config/` — `agencies.json` (단일 진실원), `safeguard_keywords.json`
- `.github/workflows/` — collector + watchdog + ci + ssl-matrix-check
- `tasks/`, `templates/`, `_runner/` — legacy harness; 기능추가에서는 사용하지 않음

## 능력 경계선

- **Gemini API**: backend `GEMINI_FILTER_MODEL` / `GEMINI_ANALYZER_MODEL`
  / `GEMINI_ANALYZER_FALLBACK_MODEL`, frontend `GEMINI_REPORT_MODEL`
  env. 호출 진입점은 `src/services/analyzer/gemini_client.py`
  (google-genai SDK) 와 `web/app/api/report/route.ts`. 새 호출이
  필요하면 새 wrapper를 만들지 말고 기존 wrapper를 확장.
- **Supabase**: `src/db/client.py` 싱글톤. 키 정책은
  `docs/secret-rotation-checklist.md`.
- **Telegram**: `src/services/notifier.py`. 외부 알림은 이 모듈 재사용.
- **Scrapers**: `src/collectors/` 아래 http / date_parser / pagination
  / list_scraper / content_scraper / sanction_scraper / rss_parser.
  새 사이트 추가 시 기존 helper 재사용 가능 여부부터 확인.
- **Agency 단일 진실원**: `config/agencies.json`. 새 기관 / 카테고리 /
  SSL 옵트아웃은 코드 수정 없이 JSON으로만 (`agency_loader`가 파생).
- **테스트**: `pytest tests/`, `cd web && npm test`. CI는
  `.github/workflows/ci.yml`. 새 코드는 단위 테스트 동반 필수.
- **Admin**: `scripts/admin/` — 파괴적 작업은 사용자 confirm 후.
- **운영 트리거**: collector는 외부 cron-job.org →
  `workflow_dispatch`(`news_collector_v2_active.yml`). watchdog만
  GHA native cron (2h).

## 시행착오 일지

production에서 한 번 겪은 함정. 새 코드 작성 시 미리 차단.

### T1. Gemini 응답 list-wrapping (`f17eb55`)
**증상**: Gemini가 `[{...}]` 또는 `{"content": [{...}]}` 형태로 응답
→ dict 가정 parser가 `TypeError` → silent `ANALYSIS_FAILED` (~3% 발생).
**규칙**: Gemini 응답 파싱 전에 root + 각 top-level section에
list-unwrap 가드 적용 (`_unwrap_if_list` 패턴).

### T2. Supabase PostgREST max-rows=1000 (`8dda069`)
**증상**: `select().execute()` 한 번으로 전체 행을 가져온다고 믿으면
1000행에서 silent truncate → dedup 누락 → unique violation crash.
**규칙**: 전체 행 조회는 반드시 1000행 윈도 페이지네이션
(`_load_existing_links` 패턴).

### T3. `str, Enum`의 `__str__` Python 3.11+ 변경 (`86b71cf`)
**증상**: `str(AgencyCode.FSS_SANCTION)` → `"AgencyCode.FSS_SANCTION"`.
supabase-py `.eq()` 0행 매치 → sanction dedup 빈 캐시 → unique violation.
**규칙**: str 직렬화 경로에 들어가는 enum은 `__str__` 명시 override.
`StrEnum`은 workflow Python 3.10 pin이라 사용 불가.

### T4. gitleaks `generic-api-key` false positive (`ecc0fe0`)
**증상**: docstring에 high-entropy literal 예시 → gitleaks가 CI를 차단.
**규칙**: 시크릿스러운 예시는 prose로 변수명만 지시 (`TEST_SECRET`),
실제 값은 fixture/beforeEach에서 정의.

### T5. 새 agency 추가 시 DB CHECK constraint + display URL 확인 (`5578620`, `9132a4b`)
**증상**: `config/agencies.json`과 frontend만 업데이트하고 live DB의
`articles_agency_check` constraint를 빠뜨려 모든 insert가 `23514`로 실패.
또한 MAFRA `/bbs/` URL은 사이트 네비게이션 없는 raw CMS 페이지여서 모바일
렌더링이 깨짐 — `enc` deep-link로 display URL을 별도 생성해야 함
(`web/utils/mafraLink.ts`). DB에는 scrape/dedup용 canonical `/bbs/` URL 유지.
**규칙**: agency 추가 시 체크리스트: (1) `agencies.json` (2) `agency_codes.py`
(3) live DB constraint (4) frontend constants/components (5) 원문 URL이
단독으로 정상 렌더링되는지 확인, 안 되면 display URL 변환 필요.
`db/schema.sql`과 `scripts/admin/update_agency_constraint.py`도 동기화.

## 코딩 원칙

- **기존 동작을 깨지 마라.** 기능추가라도 기존 경로의 입출력은 동일
  유지. 변경이 필요하면 사용자 합의 후.
- **View / UI에 비즈니스 로직 금지.** lib / hook / 백엔드로 분리.
- **문자열 리터럴 대신 enum / 상수.** 기존 enum 확장 또는 새 enum.
  (T3 주의.)
- **이전 코드의 네이밍 패턴을 따른다.** 새 패턴 도입은 사용자 합의 후.
- **중복 코드 금지.** 기존 helper 재사용 또는 공통 유틸 추출.
- **방어적 코드는 시스템 boundary에서만.** 내부 함수에 validation /
  try-except 남발 금지.
