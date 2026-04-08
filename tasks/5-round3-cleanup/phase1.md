# Phase 1: scheduler-removal

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `docs/round2-summary.md` (Round 2 종결 시 scheduler.py 처분을 후속 라운드로 미뤘던 결정)
- `docs/ARCHITECTURE.md` (현재 구조 — `scheduler.py [LEGACY/UNUSED]` 표기)
- `spec/refactor-round1.md` (Pipeline import 사이드이펙트 규약)
- `CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. **source-first**다:

- `src/scheduler.py` (이번 phase 삭제 대상, 36 LOC)
- `src/main.py` (운영 진입점)
- `src/pipeline.py` (소비처 확인용)
- `requirements.txt` (`apscheduler` 의존성 위치)

운영 진입점 확인 (수정 금지, 읽기만):

- `.github/workflows/news_collector_v2_active.yml`
- `.github/workflows/news_collector.yml`
- `.github/workflows/watchdog.yml`

위 워크플로 모두가 `python src/main.py`만 호출하고 `scheduler.py`는 어디에서도 트리거되지 않음을 직접 확인하라.

이전 phase 산출물: 없음 (이번 task의 첫 phase)

문서보다 코드가 우선이다. 의문점은 작업 중 기록하라.

## 작업 내용

이 phase는 **dead code 제거 + 의존성 제거**만 다룬다. docs/spec/scripts/web/.github 일체 손대지 않는다.

### 1. 사전 grep — 호출 경로 0건 재확인

작업 시작 전 다음 명령으로 호출 경로가 정말 0건인지 본인 눈으로 확인하라:

```bash
grep -rn "from src.scheduler\|import src\.scheduler\|src/scheduler" \
  src/ scripts/ web/ tests/ .github/workflows/ 2>/dev/null
```

만약 0건이 아니면 dead code 가정이 깨진 것이므로 즉시 `index.json`의 phase 1 status를 `"blocked"`로 바꾸고 `blocked_reason`에 발견 위치를 기록한 뒤 중단하라. 이 phase에서 자체 판단으로 import를 수정하지 마라.

### 2. `git rm src/scheduler.py`

파일 자체 삭제. 백업 디렉토리로 이동하지 마라. git history에서 복원 가능하다.

### 3. `requirements.txt`에서 `apscheduler` 라인 제거

현재 `requirements.txt:1`이 BOM(`\ufeff`) 포함 `apscheduler>=3.10.4`로 시작한다. 그 라인만 정확히 제거하라.

- 다른 라인 수정·정렬·재배열 금지.
- BOM 자체를 다른 패키지 앞으로 옮기지 마라. 라인 통째로 제거.
- 빈 줄을 끝에 남기지 마라.

### 4. 회귀 검증

작업 후 `src/`, `tests/`, `web/`, `.github/`, `docs/`, `spec/`, `config/`, `scripts/admin/`, `scripts/monitor/` 전부 무변경 상태여야 한다 (`git diff --name-only`로 확인).

## Acceptance Criteria

```bash
# scheduler.py 부재
! test -f src/scheduler.py
! git ls-files | grep -E '^src/scheduler\.py$'

# apscheduler 의존성 제거
! grep -i 'apscheduler' requirements.txt

# 호출 경로 0건 (자기 자신 제외)
! grep -rn "from src.scheduler" src/ scripts/ web/ tests/ 2>/dev/null
! grep -rn "import src\.scheduler" src/ scripts/ web/ tests/ 2>/dev/null

# requirements.txt 파싱 OK
python3 -c "
from pathlib import Path
lines = [l.strip() for l in Path('requirements.txt').read_text(encoding='utf-8-sig').splitlines() if l.strip() and not l.startswith('#')]
assert not any('apscheduler' in l.lower() for l in lines), f'apscheduler still present: {lines}'
print('requirements.txt OK, no apscheduler, %d packages' % len(lines))
"

# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"

# pytest 회귀 0
python3 -m pytest -q

# 손대지 말아야 할 디렉토리 무변경
git diff --name-only HEAD -- src/ tests/ web/ docs/ spec/ config/ scripts/admin scripts/monitor scripts/v2_schema_setup.sql 2>/dev/null | grep -v '^src/scheduler\.py$' | head
test "$(git diff --name-only HEAD -- src/ tests/ web/ docs/ spec/ config/ scripts/admin scripts/monitor scripts/v2_schema_setup.sql 2>/dev/null | grep -v '^src/scheduler\.py$' | wc -l)" = "0"
```

## AC 검증 방법

위 AC 커맨드를 순서대로 실행하라. 모두 통과하면 `tasks/5-round3-cleanup/index.json`의 phase 1 status를 `"completed"`로 변경하라.

수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고 `error_message` 필드에 구체 사유를 기록하라.

호출 경로 grep에서 예상 외 import가 발견되면 자체 판단으로 수정하지 말고 status `"blocked"` + `blocked_reason`에 위치 기록 후 중단하라.

## 주의사항

- **`docs/`, `spec/`, `.github/workflows/`, `scripts/`(전부), `web/`, `tests/`, `config/`, `src/main.py`, `src/pipeline.py`, `src/collectors/**`, `src/services/**`, `src/db/**`, `src/utils/**` 일체 수정 금지.** 이번 phase는 `src/scheduler.py` 1파일 + `requirements.txt` 1라인만.
- **`docs/`의 scheduler 언급은 phase 3에서 처리한다.** 이 phase에서 docs를 만지면 책임 경계가 깨진다.
- **`.github/workflows/*.yml` 수정 금지.** GH Actions 업그레이드는 phase 4의 책임.
- **`requirements.txt`에서 apscheduler 외 다른 라인 수정 금지.** 정렬, 공백 정리, 코멘트 추가 모두 금지.
- **`requirements-dev.txt` 수정 금지.**
- **새 파일 생성 금지.** archive 이동도 금지 — git history로 복원 가능하므로 그냥 삭제.
- **`src/utils/logger.py`의 `setup_logger` 등 scheduler.py가 사용하던 utility는 그대로 두어라.** 다른 곳에서 사용 중일 수 있고, 이번 phase가 utility 정리까지 확장되면 책임이 분산된다.
- 기존 pytest 43개를 깨뜨리지 마라.
