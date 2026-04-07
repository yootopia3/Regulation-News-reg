# Phase 4: deadcode-and-docs

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `CLAUDE.md` — phase 실행 규약.
- `tasks/3-auth-hardening/index.json` — task scope. 본 phase는 dead code 1건 삭제 + 문서 동기화 + SQL stale 표시까지만.
- `spec/refactor-round1.md` — round 1 결과 디렉토리/모듈 구조의 사실 기준. ARCHITECTURE.md 갱신 시 이 문서와 실제 코드를 교차 검증.
- `spec/backend-architecture.md` — round 1에서 확정한 모듈 경계. ARCHITECTURE.md 갱신 시 참조.

그리고 아래 핵심 소스 파일을 직접 읽어 현재 상태를 파악하라. **source-first** 다:

- `web/app/page.tsx` — `DashboardV2` 만 import 함을 재확인. 다른 import 0건이어야 함.
- `web/components/Dashboard.tsx` — 삭제 대상(현재 798 LOC).
- `web/components/dashboard/DashboardV2.tsx` — 라이브 진입점. 본 phase에서 손대지 마라.
- `web/components/ReportModal.tsx` — `Dashboard.tsx` 와 별개로 살아있는 컴포넌트. 손대지 마라.
- `README.md` — 현재 "5 Agencies", `python src/scheduler.py` 안내, 평문 passcode `marketpulse1234` 등의 사실관계가 어긋난 내용이 있다.
- `docs/ARCHITECTURE.md` — round 1 이전 디렉토리 트리 + 5 agency + `src/services/analyzer.py` 단일 파일 + `src/scheduler.py` "active" 등의 stale 내용.
- `db/schema.sql` — round 1 이전의 v1 스냅샷. CHECK 제약 + agency 5종 + `category` 컬럼 부재.
- `scripts/v2_schema_setup.sql` — v2 dev 스냅샷. `category` 컬럼 부재.
- `config/agencies.json` — agency 수의 단일 사실 출처. README/ARCHITECTURE.md의 agency 수를 갱신할 때 이 파일을 직접 읽어 확정.
- `.github/workflows/news_collector_v2_active.yml` — 운영 cron 트리거 사실의 직접 근거. README/ARCHITECTURE.md 가 GitHub Actions cron 을 안내하기 전에 이 파일을 읽어 존재/스케줄을 확인하라.

이전 phase 산출물:

- `tasks/3-auth-hardening/phase1.md` (백엔드 hygiene)
- `tasks/3-auth-hardening/phase2.md` (프론트 인증). README/ARCHITECTURE.md의 인증 안내가 phase 2에서 만들어진 `mp_session` 쿠키 + `APP_PASSCODE`/`SESSION_SECRET` 환경변수 + `/api/auth/login` route를 가리켜야 한다.
- `tasks/3-auth-hardening/phase3.md` (`/api/report` 가드)

문서보다 코드가 우선이다.

## 작업 내용

### 1. dead code 삭제 — `web/components/Dashboard.tsx`

- 삭제 전 사전 검증: `rg -n "components/Dashboard\b" web -g '*.ts' -g '*.tsx'` 결과를 확인하라. `web/components/dashboard/...`(라이브 진입점 `DashboardV2` 등)와 삭제 대상인 `web/components/Dashboard.tsx` 자체 정의 라인을 제외한 모든 매칭이 0건이어야 한다(즉 라이브 caller 0). 1건이라도 외부 import가 발견되면 즉시 phase 를 `"blocked"` 로 마킹하고 사유에 그 라인을 기록하라.
- 검증 통과 시 `web/components/Dashboard.tsx` 를 삭제(`git rm` 또는 파일 시스템 삭제).
- 다른 파일은 audit 만 하고 손대지 마라(별점 컴포넌트, 헬퍼, ReportModal 등 모두 보존).

### 2. `README.md` 동기화

코드로 검증 가능한 사실만 반영. 추측 금지.

- "5 Agencies" 표현(현 L46) → `config/agencies.json` 의 `agencies` 배열 길이를 직접 읽어 그 수로 갱신. agency 코드 목록을 나열할 경우 동일하게 `agencies.json` 을 단일 출처로 사용.
- `python src/scheduler.py` 안내(현 L18-20) 제거. 대신 다음 사실을 1~3줄로 기술:
  - 운영 진입점은 `src/main.py` 이다.
  - 운영 실행은 GitHub Actions cron(`.github/workflows/news_collector_v2_active.yml`) 으로 트리거된다.
- 평문 passcode 안내(현 L36 부근의 `**Passcode**: marketpulse1234` 라인) 제거. 대신 다음 한 단락 추가(정확히 이 내용으로):
  - 로그인은 서버에 설정된 `APP_PASSCODE` 환경변수와 비교한다.
  - 토큰 서명을 위해 `SESSION_SECRET` 환경변수도 함께 설정해야 한다.
  - 둘 중 하나라도 미설정이면 `/api/auth/login` 이 500을 반환한다.
- "Smart Analysis" 섹션의 모델 안내(현 L47-50)는 `src/config/settings.py` 의 `MODEL_FILTER_ID`, `MODEL_ANALYZER_ID` 와 일치하는지 재확인 후, 어긋나는 부분만 정정. 일치하면 그대로 둔다.
- 그 외 섹션은 손대지 마라(특히 `cd web && npm install` / `npm run dev` 흐름).

### 3. `docs/ARCHITECTURE.md` 동기화

코드로 검증 가능한 사실만 반영.

- 디렉토리 트리(현 L38-70)를 round 1 이후 실제 구조로 갱신. 다음을 반영:
  - `src/collectors/` 하위에 `http.py`, `date_parser.py`, `pagination.py`, `list_scraper.py`, `content_scraper.py`, `sanction_scraper.py`, `rss_parser.py`, `scraper.py`(facade) 가 있음(파일이 실제 존재하는지 직접 확인 후 기재).
  - `src/services/analyzer/` 가 패키지로 분해되어 있음(`hybrid.py`, `prompts.py`, `gemini_client.py`, `result_mapper.py`, `safeguards.py`). 실제 존재하는 파일만 기재.
  - `src/config/` 하위 `settings.py`, `agency_codes.py` 가 있음.
  - `src/scheduler.py` 항목은 제거 또는 "[LEGACY/UNUSED]" 로 표시.
- agency 수 표기(`agencies.json` 단일 출처)를 갱신.
- `## 4.1 Hybrid Analyzer` 섹션의 단일 파일 가정을 패키지 가정으로 갱신. 단, 함수/클래스 시그니처를 추측해서 적지 마라. 책임 한 줄과 파일 위치만 기재.
- 신규 단락: "Authentication" — `mp_session` HMAC 쿠키, `APP_PASSCODE`/`SESSION_SECRET` 환경변수, `/api/auth/login` route, `web/lib/auth.ts` 위치를 사실 기준으로 1~2단락 기재.
- 신규 단락: "Schema status" — 한 줄로 다음 톤만 허용:
  - "현재 애플리케이션 코드와 `db/schema.sql` / `scripts/v2_schema_setup.sql` 사이에 불일치가 있을 수 있다. live DB 기준으로 검증한 뒤 적용하라."
  - **`no CHECK constraint`, `category column added`, `9 agency codes are stored` 같은 단정 표현은 절대 쓰지 마라.** prod schema dump가 없는 상태에서 단정은 거짓이 될 수 있다.
- "v1.0 (Prod)" / "v2.0 (Dev/Preview)" 섹션의 환경변수 표는 `web/utils/supabase/client.ts`, `web/app/api/report/route.ts` 의 실제 사용 패턴과 일치하는지 확인 후 어긋나는 부분만 정정.

### 4. SQL 파일 stale 경고 주석

본문 변경 0줄. 파일 최상단에 주석 1~3줄만 추가.

`db/schema.sql` 최상단에 추가 (정확히 다음 톤만 허용):

```sql
-- STALE WARNING: This file may not match the live production database.
-- The application code paths in src/pipeline.py and src/collectors/ may
-- write rows whose shape this file does not describe. Verify against the
-- live database before applying this file to any environment.
```

`scripts/v2_schema_setup.sql` 최상단에 추가 (정확히 다음 톤만 허용):

```sql
-- STALE WARNING: This file may not match the live production database.
-- The application code currently writes a `category` field that is not
-- declared here. Verify against the live database before applying.
```

- **단정 표현 금지.** "no CHECK constraint", "category column added on YYYY-MM-DD", "9 agency codes are stored", "anon UPDATE policy is required" 같이 prod 사실을 단정하는 문구를 쓰지 마라. 위 두 블록의 톤(`may not match`, `verify before applying`)을 그대로 유지.
- SQL 본문(`CREATE TABLE`, `CREATE POLICY`, `CREATE INDEX`, 컬럼 정의 등)을 한 줄도 수정하지 마라.

## Acceptance Criteria

```bash
# 1. Dashboard.tsx 삭제 확인
test ! -f web/components/Dashboard.tsx

# 2. Dashboard.tsx 의 import 어디에도 없음 (path-based, quote/style 무관)
#    `web/components/dashboard/...` 하위 경로(라이브 진입점 DashboardV2 등) 매칭은 제외해야 한다.
test -z "$(rg -n "components/Dashboard\\b" web -g '*.ts' -g '*.tsx' | grep -v 'components/dashboard/')"
# DashboardV2 import 는 살아있어야 함
grep -q "from '@/components/dashboard/DashboardV2'" web/app/page.tsx

# 3. README 의 평문 passcode 흔적 0건
test -z "$(grep -n 'marketpulse1234' README.md docs/ARCHITECTURE.md)"

# 4. README 가 src/scheduler.py 명령을 안내하지 않음
test -z "$(grep -n 'python src/scheduler.py' README.md)"

# 5. README 가 APP_PASSCODE / SESSION_SECRET 환경변수를 안내함
grep -q 'APP_PASSCODE' README.md
grep -q 'SESSION_SECRET' README.md

# 6. SQL stale 경고 존재 (본문 변경은 안 함 — 첫 줄만 검사)
head -5 db/schema.sql | grep -q 'STALE WARNING'
head -5 scripts/v2_schema_setup.sql | grep -q 'STALE WARNING'

# 7. SQL 본문이 안 바뀌었음 (CREATE TABLE 라인은 그대로)
grep -q 'CREATE TABLE IF NOT EXISTS public.articles' db/schema.sql
grep -q 'create table if not exists public.articles' scripts/v2_schema_setup.sql

# 8. agencies.json 미수정
git diff --quiet config/agencies.json

# 9. task 단위 build_command 통과
venv/bin/python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer" && cd web && npm run build
```

## AC 검증 방법

위 9개 커맨드를 직접 실행하라. 모두 통과하면 phase 4 status를 `"completed"` 로 변경하고, task index의 모든 phase가 `completed` 임을 확인하라(runner가 task-level `completed_at` 을 기록한다).

수정 3회 이상 실패하면 `"error"` + `error_message` 기록.

다음은 즉시 `"blocked"`:

- `web/node_modules/` 가 존재하지 않거나 `next` 바이너리가 설치되지 않아 `cd web && npm run build` 가 환경 사유로 실패할 때(`next: not found`, `MODULE_NOT_FOUND` 등). 사용자가 사전에 `cd web && npm install` 을 1회 수동 수행해야 한다.
- `venv/` 가 존재하지 않거나 백엔드 dependencies(`pip install -r requirements.txt`)가 미설치되어 import smoke 가 환경 사유로 실패할 때.
- `web/components/Dashboard.tsx` 가 사전 rg 검증에서 1건 이상의 라이브 import를 발견될 때(예상치 못한 라이브 caller 존재).
- `config/agencies.json` 의 구조가 예상(`{"agencies": [...]}`) 과 다를 때.
- `docs/ARCHITECTURE.md` 또는 `README.md` 의 코드 검증된 사실을 기재하기 위해 prod-only 정보가 필요하다고 판단될 때(이 경우 stale 표시 톤을 유지하고 단정 문구는 회피).

## 주의사항

- **SQL 본문(테이블/정책/인덱스/컬럼 정의)을 절대 수정하지 마라.** stale 경고 주석만 추가.
- **prod schema 사실을 추측해서 단정하지 마라.** "no CHECK constraint", "category column exists in prod", "9 agency codes are stored" 등 모두 금지. `may not match` / `verify before applying` 톤만 허용.
- `web/components/Dashboard.tsx` 외 다른 파일을 삭제하지 마라.
- `web/app/api/trigger-collect/route.ts`, `web/app/api/check-collection-status/route.ts` 를 삭제하지 마라(외부 호출 여부 미확정 — 본 라운드 out-of-scope).
- `config/agencies.json` 을 수정하지 마라.
- `web/components/dashboard/DashboardV2.tsx`, `web/components/dashboard/NewsCard.tsx`, `web/components/ReportModal.tsx` 를 수정하지 마라.
- `web/utils/supabase/client.ts` 의 placeholder fallback 을 건드리지 마라.
- `analysis_result.keywords` dead branch (`web/components/dashboard/DashboardV2.tsx:140`) 정리는 본 라운드 out-of-scope.
- 새 spec 문서를 만들지 마라. 본 phase가 사용할 모든 사실은 이 phase 파일과 기존 문서/소스에 자기완결적으로 존재해야 한다.
- 본 phase에서 백엔드(`src/`), `_runner/`, `package.json` 을 수정하지 마라.
- 기존 테스트가 있다면 깨뜨리지 마라(현재 `tests/` 디렉토리는 없음).
