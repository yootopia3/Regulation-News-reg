# Phase 3: docs-stale-sweep

## 사전 준비

먼저 아래 문서를 **본문 전체** 직접 읽어라. patch 위치를 머리로 추정하지 마라:

- `docs/MASTER_CONTEXT.md`
- `docs/PRD.md`
- `docs/REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/SCHEMA.md` (이번 phase에서는 수정 안 하지만 stale 여부 확인 목적)
- `docs/round2-summary.md` (Round 2 산출물 — 수정 금지)
- `docs/implementation_plan.md` (이동 대상)
- `docs/task.md` (이동 대상)
- `spec/backend-architecture.md` (Round 1 산출물, 외과적 수정만)
- `spec/refactor-round1.md` (Round 1 산출물 — **수정 금지**)
- `CLAUDE.md`

운영 트리거 현실 직접 재확인 (이 phase에서 수정 금지, 읽기만):

- `.github/workflows/news_collector_v2_active.yml` — `# Schedule disabled - using external cron (cron-job.org)` 주석과 `workflow_dispatch:` 단독 활성 직접 확인
- `.github/workflows/news_collector.yml` — `# DISABLED: Using v2 collector now` 주석 + dispatch 단독 직접 확인
- `.github/workflows/watchdog.yml` — `schedule: - cron: '0 */2 * * *'` 활성 + `workflow_dispatch` 직접 확인

사전 grep으로 patch 대상 위치 파악:

```bash
grep -rn "scheduler\.py\|src/scheduler" docs/ spec/ 2>/dev/null | grep -v 'docs/archive'
grep -rn "feat/v2.0-upgrade" docs/ spec/ 2>/dev/null | grep -v 'docs/archive'
grep -nE "GitHub Actions.*[Cc]ron|cron.*GitHub Actions|news_collector\.yml|cron-job\.org|cron: '\\*/30" \
  docs/ spec/ 2>/dev/null | grep -v 'docs/archive'
```

이전 phase 산출물:

- Phase 1: `src/scheduler.py` 삭제 + `apscheduler` 제거. → docs에서 scheduler를 "removed"로 서술 가능.
- Phase 2: `scripts/` 루트 정리. `scripts/v2_schema_setup.sql` 위치 보존. → docs ARCHITECTURE의 해당 라인은 수정 불필요.

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **사실 정정 + 이동 + 마이너 메타 갱신**만 다룬다. **본문 rewrite 절대 금지**.

> **시점 주의**: `docs/round3-summary.md` 신규 작성과 `docs/PRD.md`의 `Status` 필드 최종화는 **이 phase가 아니라 phase 4**의 책임이다. Phase 4가 실패해도 docs상으로 Round 3가 끝난 것처럼 보이지 않게 하기 위함이다. 이 phase에서는 사실 정정만 한다.

### 3-1. Stage 4 stale 문서 archive 이동

신규 디렉토리: `docs/archive/round0/stage4/` (`git mv`로 자연 생성)

`git mv` 대상:

- `docs/implementation_plan.md` → `docs/archive/round0/stage4/implementation_plan.md`
- `docs/task.md` → `docs/archive/round0/stage4/task.md`

**이동 후 본문 수정 금지.** 역사 기록이므로 그대로 보존.

### 3-2. `docs/MASTER_CONTEXT.md` patch

본문을 직접 읽고 다음 4곳만 수정. 다른 곳은 손대지 마라.

(a) **상단 메타 갱신**:
```
- **Version**: 1.0.0
- **Last Updated**: 2025-12-24
+ **Version**: 1.1.0
+ **Last Updated**: 2026-04-08
```
`Enforcement: Absolute`는 그대로.

(b) **L18 (PRD 행의 Infrastructure 셀)**:
```
- | • **Infrastructure**: GitHub Actions ONLY (No Scheduler).<br>• ...
+ | • **Compute**: GitHub Actions for compute (`workflow_dispatch` triggered by external cron-job.org). No in-repo Python scheduler, no GitHub Actions `schedule:` block for the collector.<br>• ...
```
"Dashboard: Requires Auth (Middleware)", "Zero-Maintenance: Watchdog must run every 2h" 부분은 본문 그대로 유지.

(c) **L19 (ARCHITECTURE 행의 Modules 셀)**: `<br>• **Legacy**: \`scheduler.py\` is dead code.` 부분만 외과적 삭제. 같은 셀의 `**Modules**: pipeline.py is King`, `**Flow**: ...`는 그대로.

(d) **L43~L44 (How to Apply These Rules 항목)**:
```
- 3.  **Check Legacy**: Before editing `scheduler.py`, stop. It is deprecated.
- 4.  **v2.0 Upgrade**: When working on `feat/v2.0-upgrade`, you MUST use the v2.0 Environment Variables and Database. DO NOT touch v1.0 Production Data.
+ 3.  **Trigger Reality**: Collector is triggered by external cron-job.org via `workflow_dispatch` on `news_collector_v2_active.yml`. Watchdog uses GitHub Actions native cron (`0 */2 * * *`). The collector has no in-repo Python scheduler and no GitHub Actions `schedule:` block.
```
번호 재정렬: 기존 1, 2, 3, 4 → 1, 2, 3 (4번 v2.0 Upgrade 삭제, 3번을 Trigger Reality로 교체).

### 3-3. `docs/PRD.md` patch

**`Status` 필드는 이 phase에서 건드리지 마라.** Phase 4가 최종화한다.

(a) **L18 (Infrastructure Layer)**:
```
- - **Architecture**: 100% GitHub Actions (No idle servers).
+ - **Architecture**: GitHub Actions for compute, triggered via `workflow_dispatch` by external cron-job.org (no idle servers).
```

(b) **L20 (Legacy Removal)**:
```
- - **Legacy Removal**: Deprecated `scheduler.py` to prevent zombie processes.
+ - **Legacy Removal**: `src/scheduler.py` removed in Round 3 (was deprecated in Round 0).
```

(c) **L82 (CI/CD)**:
```
- - **CI/CD**: GitHub Actions (`news_collector.yml`, `watchdog.yml`).
+ - **CI/CD**: GitHub Actions. Active production collector: `news_collector_v2_active.yml` (triggered by external cron-job.org via `workflow_dispatch`). Watchdog: `watchdog.yml` (GitHub Actions native cron, every 2h). `news_collector.yml` is the v1 legacy file, retained for history but disabled.
```

다른 섹션은 손대지 마라.

### 3-4. `docs/REQUIREMENTS.md` patch

(a) **L16~L18 (DEPRECATED scheduler 섹션) 삭제**:
```
- **DEPRECATED**: `src/scheduler.py` (Background Scheduler).
- (이어지는 *Action*: Do not use ... 줄도 함께 삭제)
```
정확한 위치는 본문 직접 확인 후 결정. 보통 2~3줄 단위로 외과적 삭제.

(b) **L21 (Schedule 거짓 서술 정정)**:
```
- **Schedule**: Every 30 minutes (GitHub Actions `cron: '*/30 * * * *'`).
+ **Schedule**: Triggered externally by cron-job.org via GitHub `workflow_dispatch` on `news_collector_v2_active.yml`. The GitHub Actions `schedule:` block in the workflow is intentionally disabled — see workflow comment. The exact interval is configured in cron-job.org outside this repo.
```

(c) **L151 (feat/v2.0-upgrade 브랜치 언급) 삭제**:
```
- **Codebase**: Dedicated `feat/v2.0-upgrade` branch.
```
줄 단위 삭제. 주변 항목 들여쓰기·번호가 깨지지 않게 주의.

### 3-5. `docs/ARCHITECTURE.md` patch

(a) **Mermaid 다이어그램 (L12 부근) trigger 노드 정정**:
```
- Trigger[GitHub Actions Cron] -->|Periodic| Main[src/main.py]
+ Trigger[External Cron · cron-job.org] -->|workflow_dispatch| GHA[news_collector_v2_active.yml]
+ GHA --> Main[src/main.py]
```
한 줄을 두 줄로 분리하면서 새 노드 `GHA`를 도입. 다른 노드(`Pipeline`, `Scraper`, `RSS`, `Analyzer`, `Tier1`, `Tier2`, `Safeguard`, `Supabase`, `Telegram`)는 절대 건드리지 마라. mermaid 문법이 깨지면 디아그램 전체가 렌더링 실패한다.

(b) **디렉토리 트리에서 `scheduler.py` 줄 삭제 (L79 부근)**:
```
-│   └── scheduler.py            # [LEGACY/UNUSED]
```
이 줄이 디렉토리 트리의 마지막 항목이었는지 확인 후, 직전 항목의 트리 연결자(`├──` ↔ `└──`)를 필요시 정합성 맞춰 교체.

(c) **L42 (디렉토리 트리 주석) 보강**:
```
-│       └── news_collector_v2_active.yml  # Production trigger (workflow_dispatch)
+│       └── news_collector_v2_active.yml  # Production collector (triggered by external cron-job.org via workflow_dispatch)
```

다른 섹션·다른 다이어그램·다른 디렉토리 트리 entry 모두 손대지 마라.

### 3-6. `spec/backend-architecture.md` patch

`scheduler` 4곳을 외과적으로 제거 또는 정정. 본문 골격(섹션 구조, 섹션 제목, 다른 모듈 설명)은 보존.

(a) **L15 (디렉토리 트리에서 scheduler.py 줄)**:
```
-├── scheduler.py               (36 LOC)   APScheduler BlockingScheduler. 주기적 Pipeline 실행.
```
삭제. 직전/직후 트리 연결자 정합성 확인.

(b) **L42 부근 (scheduler.py 모듈 설명 항목)**:
```
- - `src/scheduler.py`: APScheduler 기반 주기 실행. `settings.COLLECTION_INTERVAL_MINUTES` ...
```
항목 통째로 삭제 (정확한 줄 수는 본문 보고 결정).

(c) **L78 (현행 유지 트리)**:
```
-├── scheduler.py               (현행 유지).
```
삭제.

(d) **L158 (import 금지 규칙)**:
```
- - `pipeline`은 `main` / `scheduler`를 import 금지.
+ - `pipeline`은 `main`을 import 금지.
```

### 3-7. `docs/round3-summary.md` 작성 — **이 phase에서 작성하지 마라**

`docs/round3-summary.md`는 phase 4에서 작성한다. 이 phase에서는 만들지 마라.

이유: round3-summary.md의 존재 자체가 "Round 3 완료" 신호로 작동한다. Phase 4가 실패할 가능성을 고려해 최종 산출물은 마지막 phase로 미룬다.

## Acceptance Criteria

```bash
# Stage 4 stale 문서 archive 이동
test -f docs/archive/round0/stage4/implementation_plan.md
test -f docs/archive/round0/stage4/task.md
! test -f docs/implementation_plan.md
! test -f docs/task.md

# scheduler 언급 제거 (archive 디렉토리는 검사 제외)
! grep -n 'scheduler\.py' docs/MASTER_CONTEXT.md
! grep -n 'scheduler\.py' docs/PRD.md || grep -nE 'removed.*scheduler\.py|scheduler\.py.*removed' docs/PRD.md
! grep -n 'scheduler\.py' docs/REQUIREMENTS.md
! grep -n 'scheduler\.py' docs/ARCHITECTURE.md
! grep -n 'scheduler\.py' spec/backend-architecture.md

# feat/v2.0-upgrade 언급 제거
! grep -n 'feat/v2.0-upgrade' docs/MASTER_CONTEXT.md
! grep -n 'feat/v2.0-upgrade' docs/PRD.md
! grep -n 'feat/v2.0-upgrade' docs/REQUIREMENTS.md

# 트리거 사실 정정 흔적
grep -q 'cron-job\.org' docs/MASTER_CONTEXT.md
grep -q 'cron-job\.org' docs/PRD.md
grep -q 'cron-job\.org' docs/REQUIREMENTS.md
grep -q 'cron-job\.org' docs/ARCHITECTURE.md
grep -q 'workflow_dispatch' docs/REQUIREMENTS.md
grep -q 'news_collector_v2_active' docs/PRD.md

# REQUIREMENTS.md의 거짓 cron 줄 제거
! grep -E "cron: '\\*/30" docs/REQUIREMENTS.md

# ARCHITECTURE.md mermaid 잘못된 노드 라벨 제거
! grep -E 'Trigger\[GitHub Actions Cron\]' docs/ARCHITECTURE.md

# MASTER_CONTEXT 메타 갱신
grep -q '\*\*Version\*\*: 1\.1\.0' docs/MASTER_CONTEXT.md
grep -q '\*\*Last Updated\*\*: 2026-04-08' docs/MASTER_CONTEXT.md

# round3-summary.md는 이 phase에서 만들면 안 됨
! test -f docs/round3-summary.md

# PRD.md Status 필드는 이 phase에서 변경하지 않음
# (Stage 2 Complete 또는 phase 4 이후 결정될 최종값과 다른 중간 형태가 아님을 보장)
grep -q '\*\*Status\*\*: Stage 2 Complete' docs/PRD.md

# Round 1 산출물 본문 무변경
git diff --quiet HEAD -- spec/refactor-round1.md
git diff --quiet HEAD -- docs/round2-summary.md

# .github/workflows/는 절대 변경되지 않았어야 함 (phase 4의 책임)
git diff --quiet HEAD -- .github/workflows/

# scripts/v2_schema_setup.sql 무변경 (phase 2가 유지하기로 한 파일, 이번 phase도 손대지 않음)
git diff --quiet HEAD -- scripts/v2_schema_setup.sql

# 임포트 / pytest 회귀 0
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
python3 -m pytest -q

# web 회귀 (npm ci 필수 — 이전 phase에서 node_modules가 비어 있을 수 있음)
cd web && npm ci && npm test && npm run build
cd -
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 3 status를 `"completed"`로 변경.

mermaid 구문 손상이 의심되면 GitHub의 mermaid live editor 또는 본인 환경의 markdown 프리뷰로 즉석 검증하라. 다이어그램이 깨지면 디스플레이 전체가 무너지므로 신중하게.

3회 이상 실패 시 `"error"` + `error_message`. 사용자 개입 필요 시 `"blocked"`.

## 주의사항

- **이번 phase는 사실 정정만.** 본문 골격, 섹션 순서, 문장 스타일을 보존하라. rewrite 금지.
- **`docs/round3-summary.md` 작성 금지.** 그건 phase 4의 책임. 이 phase에서 만들면 Phase 4 실패 시 docs가 거짓말한다.
- **`docs/PRD.md`의 `Status` 필드 변경 금지.** Phase 4가 최종화한다.
- **`.github/workflows/*.yml` 절대 수정 금지.** action 버전 업그레이드는 phase 4의 책임이고, 트리거 메커니즘 자체는 운영 사실로 유지된다.
- **`spec/refactor-round1.md` 수정 금지.** 역사 문서.
- **`docs/round2-summary.md` 수정 금지.** Round 2 산출물.
- **`docs/SCHEMA.md` 수정 금지.** stale 아니다.
- **`docs/archive/**` 하위 (Round 0/1/2 산출물) 절대 수정 금지.**
- **운영 트리거 메커니즘을 바꾸지 마라.** 현재 운영은 external cron-job.org → workflow_dispatch이고, 이 phase는 단지 그 사실을 문서에 반영할 뿐이다. 워크플로 yaml은 손대지 않는다.
- **`MASTER_CONTEXT.md`의 핵심 철학 문구(Four Pillars, Core Principles)는 보존하라.** 사실 오류만 외과적으로 정정.
- **버전 표기 (`1.0.0` → `1.1.0`)는 `MASTER_CONTEXT.md`에서만.** PRD/REQUIREMENTS의 Version은 손대지 마라.
- **새 스크린샷·이미지 추가 금지.**
- **`CLAUDE.md`, `README.md` 수정 금지.** 사용자 소유.
- **phase 1, 2 산출물(scheduler.py 부재, scripts archive 이동)을 되돌리지 마라.**
- 기존 pytest/vitest를 깨뜨리지 마라.
