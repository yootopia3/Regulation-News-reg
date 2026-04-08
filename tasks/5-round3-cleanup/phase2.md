# Phase 2: scripts-cleanup

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/refactor-round1.md` §3 (`scripts/debug/`는 Round 2에서 archive로 옮겨졌고, 루트 dump 정리를 다음 라운드로 미뤘던 맥락)
- `docs/round2-summary.md`
- `docs/ARCHITECTURE.md` (특히 L50, L180 — `scripts/v2_schema_setup.sql`을 참조하는 위치)
- `tasks/3-auth-hardening/phase3.md`, `tasks/3-auth-hardening/phase4.md` (`v2_schema_setup.sql` 추가 참조)
- `CLAUDE.md`

그리고 아래를 직접 확인하라. **source-first**다:

- `ls scripts/` — 루트 파일 목록 직접 확인
- `ls scripts/admin/` — **수정 금지** 디렉토리 (운영 admin 도구 11개)
- `ls scripts/monitor/` — **수정 금지** 디렉토리 (`watchdog.py`)
- `diff scripts/reanalyze_null_articles.py scripts/admin/reanalyze_null_articles.py` — 두 파일이 다르다는 것 + admin/ 버전이 정식이라는 것 직접 확인

사전 grep으로 살아있는 참조 위치 재확인:

```bash
grep -rn "v2_schema_setup\|fix_env_encoding\|make_transparent\|full_migration_v2\|seed_v2_data\|v2_add_category_column\|v2_emergency_drop_constraint\|v2_fix_agency_constraint" \
  docs/ spec/ src/ web/ .github/ scripts/admin/ scripts/monitor/ tests/ 2>/dev/null \
  | grep -v 'docs/archive'
```

이전 phase 산출물:

- Phase 1: `src/scheduler.py` 삭제, `requirements.txt`에서 `apscheduler` 제거. 이번 phase는 phase 1 산출물에 의존하지 않으나 무결성 유지를 위해 기존 변경을 되돌리지 마라.

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **파일 이동·삭제만** 다룬다. 새 파일 생성 금지(이동만), 기존 파일 내용 수정 금지.

### 1. archive 디렉토리 신규 생성

git이 빈 디렉토리를 추적하지 않으므로 아래 디렉토리는 **첫 번째 `git mv`가 수행되면서 자연 생성**된다. 별도 `mkdir` 또는 `.gitkeep` 작업 금지.

- `scripts/archive/round2/oneoff-tools/`
- `scripts/archive/round2/v2-migration/`

> 디렉토리 명이 `round2`인 이유: 이 파일들은 Round 2 직전(2026-04-05) baseline에서 git tracked였던 것들이다. Round 2 spec(`refactor-round1.md`)이 이를 "out-of-scope, 다음 라운드로 미룬다"고 명시했고, Round 3가 그 다음 라운드다. 디렉토리명은 출처 라운드를 가리킨다.

### 2. 루트 중복 삭제 (`git rm`)

- `git rm scripts/reanalyze_null_articles.py`

`scripts/admin/reanalyze_null_articles.py`는 절대 건드리지 마라. 정식 위치이며 더 정제된 버전이다 (`project_root` 경로 처리 + 환경변수 처리가 다름).

### 3. `git mv` — `scripts/archive/round2/oneoff-tools/`로 이동 (4개)

- `scripts/fix_env_encoding.py`
- `scripts/make_transparent.py`
- `scripts/make_transparent_black.py`
- `scripts/make_transparent_smart.py`

### 4. `git mv` — `scripts/archive/round2/v2-migration/`로 이동 (6개)

- `scripts/full_migration_v2.py`
- `scripts/seed_v2_data.py`
- `scripts/v2_add_category_column.sql`
- `scripts/v2_emergency_drop_constraint.sql`
- `scripts/v2_fix_agency_constraint.sql`
- `scripts/v2_fix_agency_constraint_force.sql`

### 5. 유지 (수정·이동 금지)

- `scripts/v2_schema_setup.sql` ← `docs/ARCHITECTURE.md:50,180` 및 `tasks/3-auth-hardening/phase3.md`, `phase4.md`에서 살아있는 참조. 위치 변경 시 docs 링크가 깨지고 phase 3에서 또 손봐야 한다.
- `scripts/admin/**` 11개 파일 (`clean_sanction_duplicates.py`, `collect_fss_personnel.py`, `delete_recent_reg.py`, `delete_target_sanctions.py`, `delete_target_sanctions_v2.py`, `fix_rss_dates.py`, `reanalyze_articles.py`, `reanalyze_null_articles.py`, `recollect_sanctions.py`, `run_backfill_safe.py`, `update_agency_constraint.py`)
- `scripts/monitor/watchdog.py`
- `scripts/archive/debug-round0/**` (Round 2 산출물)

## Acceptance Criteria

```bash
# 루트 중복 삭제
! test -f scripts/reanalyze_null_articles.py

# 루트에서 사라져야 할 파일들
for f in fix_env_encoding.py make_transparent.py make_transparent_black.py make_transparent_smart.py \
         full_migration_v2.py seed_v2_data.py \
         v2_add_category_column.sql v2_emergency_drop_constraint.sql \
         v2_fix_agency_constraint.sql v2_fix_agency_constraint_force.sql; do
  if test -f "scripts/$f"; then echo "FAIL: scripts/$f still in root"; exit 1; fi
done

# archive 위치에 존재
test -f scripts/archive/round2/oneoff-tools/fix_env_encoding.py
test -f scripts/archive/round2/oneoff-tools/make_transparent.py
test -f scripts/archive/round2/oneoff-tools/make_transparent_black.py
test -f scripts/archive/round2/oneoff-tools/make_transparent_smart.py
test -f scripts/archive/round2/v2-migration/full_migration_v2.py
test -f scripts/archive/round2/v2-migration/seed_v2_data.py
test -f scripts/archive/round2/v2-migration/v2_add_category_column.sql
test -f scripts/archive/round2/v2-migration/v2_emergency_drop_constraint.sql
test -f scripts/archive/round2/v2-migration/v2_fix_agency_constraint.sql
test -f scripts/archive/round2/v2-migration/v2_fix_agency_constraint_force.sql

# 유지 대상 보존
test -f scripts/v2_schema_setup.sql
test -d scripts/admin
test -d scripts/monitor
test -f scripts/admin/reanalyze_null_articles.py
test -f scripts/monitor/watchdog.py

# admin/monitor/v2_schema_setup.sql diff 0 (수정 안 됨)
git diff --quiet HEAD -- scripts/admin scripts/monitor scripts/v2_schema_setup.sql

# git이 rename으로 인식했는지 확인 — staged 영역에서 rename 카운트 검사
# (commit 전 단계에서도 동작. git log --follow는 commit 전이라 사용 금지)
RENAME_COUNT=$(git diff --cached --name-status 2>/dev/null | grep -c '^R' || true)
DELETE_COUNT=$(git diff --cached --name-status 2>/dev/null | grep -c '^D' || true)
echo "staged renames: $RENAME_COUNT, staged deletes: $DELETE_COUNT"
# 최소 1개 rename은 있어야 함 (10개 mv 중 git이 rename으로 잡는 건 내용 기반이라 정확한 수치는 보장 불가)
# 그러나 단순 삭제(reanalyze_null_articles.py)가 있으므로 D 카운트도 최소 1
[ "$DELETE_COUNT" -ge 1 ] || { echo "FAIL: expected at least 1 staged delete"; exit 1; }

# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"

# pytest 회귀 0
python3 -m pytest -q
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 2 status를 `"completed"`로 변경.

> **Rename 검증 주의**: phase 끝에서 runner가 commit하기 전에는 staged 상태이므로 `git log --follow`는 빈 결과를 낼 수 있다. 따라서 위 AC는 `git diff --cached --name-status`로 staged 영역에서 rename(`R`) / delete(`D`) 카운트만 검사한다. git이 일부 mv를 rename으로 인식하지 않고 add+delete로 분리할 수도 있으므로(파일 내용 변경 임계치에 따라) rename 카운트의 정확한 수치는 강제하지 않는다. 핵심 검증은 "원본 위치 부재" + "archive 위치 존재"다.

3회 이상 실패 시 `"error"` + `error_message`. 사용자 개입 필요 시 `"blocked"`.

## 주의사항

- **`scripts/admin/**`, `scripts/monitor/**` 어떤 파일도 수정·이동·삭제 금지.** 운영 도구다.
- **`scripts/v2_schema_setup.sql`은 위치·내용 모두 변경 금지.** docs ARCHITECTURE.md 참조 중.
- **`scripts/archive/debug-round0/`** (Round 2 산출물) 건드리지 마라.
- **반드시 `git mv` 사용.** 일반 `mv` + `git add`/`rm` 조합은 git이 rename 추적을 잃을 수 있다.
- **이동한 파일의 내용은 절대 수정하지 마라.** STALE WARNING 헤더 추가, 주석 정리, 들여쓰기 변경 모두 금지. 단순 이동만.
- **`.gitignore` 수정 금지.** Round 2가 이미 처리.
- **`requirements.txt`, `requirements-dev.txt` 수정 금지.**
- **새 파일 작성 금지.** 빈 `.gitkeep` 같은 파일도 만들지 마라.
- **`scripts/reanalyze_null_articles.py`(루트)와 `scripts/admin/reanalyze_null_articles.py`가 동일 내용으로 변해 있는 경우라도 admin/ 버전을 정식으로 보고 루트 버전만 삭제하라.** 머지·replace 금지.
- **phase 1 변경 결과(scheduler.py 부재, requirements.txt apscheduler 제거)를 되돌리지 마라.**
- 기존 테스트를 깨뜨리지 마라.
