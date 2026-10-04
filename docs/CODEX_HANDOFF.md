# Regulation-News-Reg Handoff

기준: 2026-10-04, 회사 원본 저장소 `C:\Users\yooto\Desktop\Regulation-News-reg`.
준비 상태: **READY WITH MANUAL SETUP — Cloud 환경 선택·설치 및 CI 버전 재검증 필요**.
과거 Google/Gemini 키는 사용자가 폐기·미사용을 확인하고 branch commit/push 진행을 승인했다.
Cloud 환경은 아직 생성하지 않았다. 원격 반영 상태는 아래 작업 branch와 `git ls-remote`로 확인한다.

## 1. Project Purpose

금융 규제기관의 보도자료·제재공시를 수집하여 웹 대시보드와 텔레그램으로 전달한다.
제재공시는 공개 원문을 요약하고 당행 본부의 부서·업무 후보와 사고예방 점검 질문·자료 예시를 제안한다.
당행 위반 또는 확정된 업무분장을 의미하지 않는다.

## 2. Current Architecture

- `src/main.py` → `src/pipeline.py` → `src/collectors/` → `src/services/analyzer/` → Supabase/Telegram.
- `config/agencies.json`이 기관 설정의 단일 원천. `src/db/client.py`는 Supabase 클라이언트 경계.
- 웹: `web/`, Next.js 16.1.0 / React 19.2.3, App Router, Vercel. 일반 세션은
  `web/lib/auth.ts`, 관리자 권한은 `web/lib/admin-auth.ts`의 Supabase Auth/허용 ID 검사로 분리.
- 내부 HWP: `src/services/internal_documents/worker.py`와 격리 parser. 일반 수집기와 분리.
- 제재 분석: `src/services/sanction_inspections/worker.py` → FSS PDF 추출 → 공개 사실 추출 →
  활성 업무원장(`master_engine.py`) 또는 검토된 직제규정(`engine.py`)에 부서 연결.
  OpenAI Responses API 진입점은 `client.py`. 모델은 환경변수 설정이며 이번 작업에서 변경하지 않았다.
- 수집: cron-job.org → `news_collector_v2_active.yml`의 workflow_dispatch.
  성공한 수집 → `sanction_automation.yml` → `batch.py` → 웹 자동게시 API.
  해당 workflow는 main을 checkout하며 현재 기본 batch limit은 3이다.
- 일반 기사 Gemini 경로와 제재 OpenAI 경로는 별개. 수집 workflow는 현재 `GEMINI_ENABLED=false`를 지정한다.
- `web/vercel.json`은 Next.js framework만 지정한다. 실제 Vercel 환경설정과 운영 DB 상태는 이번에 변경·재검증하지 않았다.

## 3. Current Focus

회사 PC의 미커밋 기능을 보존하고 Cloud 재개에 필요한 맥락·검증·보안 상태를 기록하는 작업이다.
시작 시 main/HEAD/origin/main은 `852291110b13030df6d4e7e823515d6878f0e93e`
(`Remove empty AI summary placeholder from news cards`)로 같았다. fetch 성공, ahead/behind 0/0.
시작 시 12개 수정 + 5개 미추적, staged 및 미push 커밋 없음.
`web/next-env.d.ts` 자동생성 차이만 HEAD 기준으로 복구. 원래 기능 변경 16개는 보존했다.
이번 추가 변경은 AGENTS.md 보완, 본 문서, 루트 `.env.local` ignore 규칙이다.

작업 branch: `chore/codex-cloud-handoff`. 기존 기능과 인계 준비를 두 commit으로 분리한다.
과거 태그는 push하지 않으며, 이 작업 branch의 커밋 이력만 원격에 보존한다.
main merge, force push, history rewrite, tag 생성, production deploy/migration은 승인 범위 밖이다.

## 4. Recently Implemented

아래는 **이 인계 branch에 포함하는 구현**이다. main 반영 또는 운영 배포 완료를 뜻하지 않는다.

| 파일 | 변경 |
|---|---|
| `src/services/sanction_inspections/engine.py` | organization-v2: 허용된 candidate_id로 조직명·조문을 함께 선택, 서버 원문 인용 연결, 후보 1,000개 제한 |
| `src/services/sanction_inspections/models.py` | MatchContent 공통 필드 분리, 기존 Match 필드 유지 |
| `src/services/sanction_inspections/master_engine.py` | duty-master-v2: 공개 원문 페이지를 매칭 context에 포함, 사건 맥락 보존 및 부서 판단 기록 검증 |
| `web/lib/inspection-ui.ts` | 포함·제외·유보 타입, 오류 메시지, 부서별 그룹화 |
| `web/components/DepartmentAssessments.tsx` (신규) | 관리자 전용 적용대상·역할·판단 이유·공개 인용 표시 |
| `web/app/admin/inspections/page.tsx` | 관리자 상세 화면 연결 |
| `tests/unit/test_duty_master_inspections.py` | 판단 기록 fixture/검증 보강 |
| `tests/unit/test_organization_inspections.py` | 후보 ID·원문 인용·중복·한도 테스트 |
| `tests/unit/test_duty_context_review.py` (신규) | 원문 전달, 판단 모순·누락, 인용 및 context 한도 테스트 |
| `web/__tests__/components/department-assessments.test.tsx` (신규) | 표시·호환·그룹화·비공개 필드 유출 방지 테스트 |
| `docs/ARCHITECTURE.md`, `docs/SCHEMA.md` | 데이터 흐름·private JSONB 필드 설명 |
| `docs/duty-master-setup.md`, `docs/organization-regulation-setup.md` | 실행·검증 규칙 보완 |
| `docs/superpowers/plans/2026-09-18-organization-choice-fix.md` (신규) | 기존 조직 선택 수정 계획 |
| `docs/superpowers/plans/2026-09-21-duty-context-review.md` (신규) | 기존 사건 맥락 검토 계획 |

## 5. Important Design Decisions

- 요약에서 빠질 수 있는 고객 유형·경고 전달·업체별 대응을 매칭 단계에서 공개 원문으로 재확인한다.
- 조직명과 조문을 독립 생성하면 잘못된 조합이 생길 수 있어 후보 ID로 제한하고 서버가 근거를 복원한다.
- 원장 ID는 같은 부서끼리 연결하며 지적사항·부서 중복 및 범위 밖 ID를 거부한다.
- 판단 상태값은 `included`, `excluded`, `uncertain`. 포함 집합은 matches의 업무 ID 집합과 일치해야 한다.
  인용은 해당 공개 페이지의 연속된 구간이어야 한다. 이 검증이 업무분장의 의미적 정확성을 보증하지는 않는다.
- 업무원장 `basis`는 `explicit`, `inferred`, `limited`. 자료 부족·미매칭은 자동게시 검토 대상이다.
- 관리자 판단 기록·원장 출처·내부 원문은 공개 report/Excel DTO에서 제외한다.
- 이번 `department_assessments`는 기존 JSONB 확장으로 별도 migration 없음.
- 현 모델 유지가 사용자 결정이다. Astra 샘플 분석은 운영 모델·게시본 교체 승인이 아니다.

## 6. Database / Data Flow

- `articles`: 수집된 공개 공시/기사 및 공개 분석 필드.
- `internal_documents`, `internal_document_units`, `internal_document_jobs`, `internal_document_events`,
  `internal_admin_limits`, private Storage bucket: 내부 문서 업로드·추출·검토·활성화.
- `inspection_duty_masters`: 불변 version/fingerprint를 가진 활성 업무원장. 활성 원장이 없을 때만
  검토된 활성 organization 문서 경로를 사용하며 allocation fallback은 없다.
- `sanction_inspections`: queued/processing/needs_review/failed/stale 및 private 결과·review_revision.
  `automation_status`: none/pending/published/needs_attention/manual.
- `sanction_publications`: 검증된 공개 DTO snapshot, published/withdrawn, manual/automatic.
  `inspection_review_events`: 검토·게시 이력. lease/revision/CAS 및 문서 버전 검증으로 충돌 방지.
- `web/lib/publication.ts`, `publication-service.ts`, `inspection-automation.ts`가 게시 검증 경계.
- 관련 migration: `db/migrations/202609100001_internal_documents.sql`, `202609100002_sanction_inspections.sql`,
  `202609100003_inspection_publications.sql`, `202609170001_sanction_automation.sql`,
  `202609180001_organization_basis.sql`, `202609200001_duty_masters.sql`, `202609200002_single_inspection_claim.sql`.
  기존 schema snapshot을 신규 DB에 임의 실행하지 말고 migration 순서·기존 schema를 확인한다.

## 7. External Services

Supabase(Auth/Postgres/Storage), OpenAI(제재), Gemini(일반 기사/보고서), Telegram,
GitHub Actions, cron-job.org, Vercel 및 규제기관 공개 사이트를 사용한다.
Cloud의 mock 단위 테스트·PGlite·빌드에는 운영 서비스 연결이나 실제 API 키가 필요 없다.

| 환경변수 | 용도 / 필요한 시점 | secret 여부 |
|---|---|---|
| `NEXT_PUBLIC_USE_V2_DB` | 웹 DB 선택, 실제 UI 연결 시 | 아니오 |
| `NEXT_PUBLIC_SUPABASE_URL_V2`, `NEXT_PUBLIC_SUPABASE_URL` | 웹 선택 DB URL | 아니오 |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY_V2`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | 웹 공개 클라이언트 연결 | 공개용 키; RLS 필요 |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Python DB 연결 설정 | URL/anon은 공개용 |
| `SUPABASE_SERVICE_ROLE_KEY` | 서버/worker private DB 접근 | 예; 기본 Cloud 개발에 등록하지 않음 |
| `APP_PASSCODE`, `SESSION_SECRET` | 일반 웹 로그인·서명, 로컬 UI 실행 시 | 예; 필요하면 개발 전용 값 |
| `INTERNAL_DOCUMENTS_ENABLED`, `ADMIN_USER_IDS` | 관리자 기능·허용 사용자 설정 | 플래그는 아니오, ID 목록은 관리정보 |
| `OPENAI_API_KEY` | 명시적으로 승인된 제재 실분석 | 예 |
| `OPENAI_INSPECTION_MODEL` | 실분석 모델 선택, 기존 운영 값 유지 | 아니오 |
| `OPENAI_INSPECTION_POLICY_CONFIRMED`, `SANCTION_INSPECTIONS_ENABLED` | 실분석 동의·활성 게이트 | 아니오 |
| `SANCTION_AUTOMATION_ENABLED`, `SANCTION_AUTOMATION_SINCE`, `SANCTION_BATCH_LIMIT`, `SANCTION_WEB_URL` | 운영 batch 제어 | 아니오; Cloud setup에서 비활성 유지 |
| `SANCTION_AUTOMATION_TOKEN` | batch → 웹 자동게시 인증 | 예 |
| `GEMINI_ENABLED`, `GEMINI_FILTER_MODEL`, `GEMINI_ANALYZER_MODEL`, `GEMINI_ANALYZER_FALLBACK_MODEL`, `GEMINI_REPORT_MODEL` | 일반 분석 활성·모델 | 아니오 |
| `GEMINI_API_KEY` | 명시적으로 활성화한 Gemini 분석 | 예 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 운영 알림 | 토큰은 예, chat ID는 비공개 대상정보 |
| `GITHUB_TOKEN`, `GITHUB_REPOSITORY` | 웹 수집 실행/상태 GitHub API | 토큰은 예, 저장소명은 아니오 |

GitHub Actions의 `SUPABASE_SERVICE_ROLE_KEY_V2` secret은 workflow에서
런타임 `SUPABASE_SERVICE_ROLE_KEY`로 매핑한다. Vercel 배포용 token은 소스 테스트에 필요 없다.
DB password도 PGlite 테스트에 필요 없으며 이번 준비에서 요구하지 않는다.

## 8. Known Issues / Constraints

### Security gate

2026-10-04 재검사: 현재 tracked/untracked 소스와 로컬 `.env`의 credential 대조,
OpenAI/Supabase/JWT/Google/GitHub/Vercel/DB URL/개인키 등의 패턴 및 credential literal 검사.
모든 로컬 ref에서 접근 가능한 360 commits / 1,153 unique blobs(233,240,440 bytes) 검사.
값은 출력·저장하지 않았다. gitleaks CLI는 없어 CI의 전체 규칙 실행을 대체했다고 주장하지 않는다.
reflog-only/unreachable 객체, 내려받지 않은 원격 이력, 이미지 OCR, 키의 실시간 유효성은 검사하지 않았다.

- 현재 파일에서는 실제 키 미검출. `.env.example`의 `SANCTION_AUTOMATION_TOKEN`은 설명용 placeholder로 확인된 오탐.
- `.env`, `web/.env`, `web/.env.local`은 존재하지만 미추적·ignore 적용. 루트 `.env.local`은 현재 없으며 ignore 규칙 추가.
- `.env.example`, `web/.env.local.example`의 키 항목은 비어 있거나 placeholder.
  추적 중인 `notepad.env`의 키도 placeholder이며 실제 설정용으로 사용하지 말 것. 무관한 파일 삭제는 하지 않았다.
- **실제 형식의 Google/Gemini 키 의심 노출:** 과거 `update_env.py:4`, 추가 `d44b124`, 삭제 `3b4a92c`.
- Supabase **anon** JWT: 과거 `scripts/setup_frontend_v2.py:17`, `scripts/setup_v2_env.py:8`, `c155672`.
  service_role 키가 아니므로 동일 위험으로 취급하지 않는다.
- 위 과거 commit은 현재 main 계보가 아닌 오래된 로컬 태그에서 접근 가능.
  origin의 해당 태그 조회에서는 미검출. `--tags` 일괄 push 금지. 이력 수정·키 교체 미실행.
- **문서상 별도 미확인:** `docs/secret-rotation-checklist.md`에는 `web/.env.local`의
  `89c8750` 추가/`5b029d3` 삭제와 passcode/session/Supabase/Gemini/Telegram 교체 체크가 미완료로 남아 있다.
  이 두 commit 객체는 현재 로컬에서 조회되지 않아 재검증 불가. 문서의 내용을 이번 스캔의 발견 사실과 혼동하지 말 것.
- 사용자가 과거 Google/Gemini 키 폐기·미사용을 확인하고 후속 commit/push를 승인했다.
  해당 키를 유효한 운영 secret으로 취급하지 않는다. 기존 rotation checklist의 다른 항목은
  완료로 바꾸지 않았다. 이 branch의 현재 파일에서는 실제 credential이 발견되지 않았다.

### Reproducibility / scope

- Node/Python 버전 파일은 없음. CI는 Node 20 / Python 3.10, 이번 회사 PC 검증은 Node 24.16.0 / Python 3.12.14.
  Cloud에서 CI 버전으로 재검증 필요. 기존 전역 환경은 변경하지 않았다.
- npm은 `web/package-lock.json`으로 재현. Python requirements는 범위 지정이며 완전한 버전 잠금은 아님.
- 원본의 `.venv`에는 google-genai/feedparser 등 누락. 별도 venv에 requirements 설치 후 전체 검사 성공.
- 이 작업 branch를 push한 뒤 clone하면 기능 파일 16개와 인계 변경을 함께 복원할 수 있다.
  main을 clone하는 것만으로는 이 branch의 기능을 얻을 수 없다.
- DB 데이터·활성 업무원장 payload·원본 HWP·회사 네트워크 드라이브·로컬 HTML 비교자료는 GitHub 복원 대상이 아님.
  기본 테스트에는 필요 없으며 Cloud로 자동 업로드하지 않는다.
- 빌드에 `next/font/google`의 Geist 다운로드가 필요. 설치는 npm/PyPI, 빌드는 fonts.googleapis.com/fonts.gstatic.com 접근 필요.
  화면 Pretendard는 jsDelivr 사용. 제재 HTTP wrapper는 `trust_env=False`이므로 Cloud proxy 환경에서
  실분석 네트워크를 임의 우회하지 말고 별도 확인한다.
- npm 설치에 dependency deprecation 경고 있음. 이번 범위에서 업데이트하지 않았다.
- 기존 ARCHITECTURE/SCHEMA에는 초기 단계의 배포 미적용 표현이 남아 있다. 코드 구현과 운영 적용 상태를 구분한다.

### Verification evidence (2026-10-04)

`python`은 새 격리 venv의 실행 파일을 의미한다. 웹 설치·전체 테스트·빌드는 원본 working tree에서
복사한 검증 스냅샷에서 수행했고 실제 환경파일을 복사하지 않았다. GitHub 새 clone 또는 Cloud 실행을 한 것은 아니다.

| 실제 명령 | 결과 |
|---|---|
| `python -m pip install -r requirements-inspections.txt -r requirements-dev.txt -r requirements-documents.txt` | PASS: 격리 venv 설치 |
| `python -B -m pytest -p no:cacheprovider tests -q` | PASS: 241 tests |
| `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests -q` (기존 venv) | FAIL: 패키지 누락으로 collection 15 errors. 코드 변경 없이 새 venv에서 해결 |
| `npm ci --no-audit --no-fund` | PASS: 기존 lockfile, 670 packages |
| `npm test -- --maxWorkers=2 --minWorkers=1 --no-cache` | PASS: 26 files / 156 tests. 첫 시도는 Windows sandbox의 esbuild 경로 접근 제한, 허용 실행에서 통과 |
| `npm run test:documents-db` | PASS: PGlite migration/권한/lease/게시/원장 5 scripts, 운영 DB 사용 없음 |
| `node node_modules/typescript/bin/tsc --noEmit --incremental false` | PASS: 새 lockfile 설치·build 후 스냅샷에서 exit 0 재확인 |
| `node node_modules/eslint/bin/eslint.js . --no-cache` | PASS: 새 lockfile 설치 스냅샷 전체 lint, exit 0, 오류·경고 없음 |
| `npm run build` (`NEXT_TELEMETRY_DISABLED=1`) | PASS: Next.js 16.1.0 Turbopack, 실제 키 없이 로컬 build만 수행 |
| CI gitleaks / Cloud Node20·Python3.10 / 실제 서비스 통합 | NOT RUN: 도구·Cloud 환경 미구성 및 운영 접근 제외 |

앞선 관련 테스트는 backend 103개 PASS. frontend 관련 49개 중 Excel 내보내기 1개가 병렬 실행 시
5초 timeout이었으나 동일 제한 단독 실행과 이번 전체 156개 재검사에서 모두 PASS. 재현된 신규 코드 실패 없음.
전용 Python lint/typecheck 설정은 저장소 CI에 없으며 이번에 도구·규칙을 새로 추가하지 않았다.
최종 원본 `next-env.d.ts` diff 없음. 원본 기능 파일 16개는 해시 비교로 내용 보존 확인.
commit 전 인계 대상은 13개 tracked 수정 + 6개 untracked = 19개였다. main의 기준 SHA는 유지한다.

## 9. Next Recommended Tasks

1. 기존 rotation checklist의 나머지 미확인 항목은 실서비스 연결 전에 별도 확인. 폐기 확인된 과거 Google 키는 재사용하지 않는다.
2. 이 작업 branch의 기능 commit과 인계 commit을 검토하고 원격 SHA를 확인한다.
3. main merge/운영 deploy는 별도 승인 범위이며 Cloud 개발 시작을 위해 필요하지 않다.
4. Cloud에서 CI 버전으로 아래 명령 재실행. 현재 로컬 태그를 Cloud로 이관할 필요 없음.
5. 코드 주석의 TODO를 새 기능 요구로 확대하지 말고 사용자 요청을 기준으로 다음 개발 선택.
   이번 핵심 모듈/관리자 컴포넌트에서는 추가 TODO/FIXME를 찾지 못했다.

## 10. How to Resume

먼저 읽기: `AGENTS.md` → 이 문서 → `docs/ARCHITECTURE.md` → `docs/SCHEMA.md` →
관련 기존 계획 2개 → `engine.py`, `master_engine.py`, `worker.py`, `web/lib/publication.ts` 및 관련 테스트.

Cloud 설정은 [공식 환경 안내](https://learn.chatgpt.com/docs/environments/cloud-environment)를 기준으로 한다.
2026-10-04 문서는 Codex Cloud (Legacy)로 표시되며, 계정에서 해당 환경 UI를 사용할 수 있는지는 별도 확인 필요.
repository `yootopia3/Regulation-News-reg`, **push 완료 후** 작업 branch 선택.
branch가 선택 목록에 없으면 GitHub 연결 권한과 원격 push 상태를 확인한다.

CI에 맞춰 런타임 Python 3.10 / Node 20을 환경 설정에서 선택한다. 새 setup script 파일은 불필요하며
환경의 setup 입력란에서 저장소 root 기준 아래 명령을 사용할 수 있다.

```bash
set -eu
python --version
node --version
python -m venv .venv
.venv/bin/python -m pip install -r requirements-inspections.txt -r requirements-dev.txt -r requirements-documents.txt
npm --prefix web ci --no-audit --no-fund
```

setup의 activate/export가 다음 agent 세션에 유지된다고 가정하지 말고 `.venv/bin/python` 경로를 직접 사용한다.
기본 개발에서는 실제 키를 등록하거나 .env를 만들 필요 없다. 필요 시 환경 설정에 비밀이 아닌
`NEXT_TELEMETRY_DISABLED=1`, `GEMINI_ENABLED=false`, `SANCTION_INSPECTIONS_ENABLED=false`,
`SANCTION_AUTOMATION_ENABLED=false`, `INTERNAL_DOCUMENTS_ENABLED=false`를 지정한다.
단위 테스트는 자체 mock/stub를 사용한다.

```bash
.venv/bin/python -B -m pytest -p no:cacheprovider tests -q
cd web
npm test -- --maxWorkers=2 --minWorkers=1 --no-cache
npm run test:documents-db
npx tsc --noEmit --incremental false
npm run lint -- --no-cache
npm run build
git status --short
git diff -- next-env.d.ts
```

새 clone에서는 Next route 생성 타입이 없을 수 있으므로 build 후 typecheck로 재확인한다.
build/dev가 next-env.d.ts를 바꾸면 이번처럼 자동생성 경로 차이인지 확인하고 커밋 대상에서 제외한다.
setup은 npm/PyPI 다운로드가 필요하고, agent 단계의 mock 테스트는 네트워크 불필요.
agent 단계 build를 위해 Google Fonts 도메인만 추가 허용할 수 있다. 실수집·실분석·운영 DB는 기본 허용하지 않는다.
공식 Cloud 문서상 secrets는 setup 단계에서만 제공된다. 이를 파일로 옮겨 agent에 노출하는 우회를 하지 않는다.
실서비스 연동이 필요하면 별도 승인된 개발환경 credential과 지원되는 전달 방식을 확인한다.

GitHub 연결에는 이 저장소를 읽을 권한, 향후 branch/PR 제출에는 그에 맞는 쓰기 권한이 필요하다.
Vercel 재연결·운영 secrets 복제·Supabase migration은 기본 개발에 필요 없다.
집 PC에서는 동일한 ChatGPT 계정/워크스페이스로 Cloud에 로그인하여 같은 Cloud 작업을 열어 이어간다.
새 작업을 열면 동일 repository/작업 branch를 선택하고 위 문서를 읽도록 요청한다.
로컬 대화·미커밋 파일·.env가 PC 사이에서 자동 동기화되는 것으로 가정하지 않는다.
