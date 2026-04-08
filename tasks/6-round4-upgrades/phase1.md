# Phase 1: GitHub Actions checkout/setup-python 버전 업그레이드

## 사전 준비

먼저 아래 문서를 읽어 phase 실행 규칙과 Round 4 의 변경 원칙을 파악하라:

- `CLAUDE.md` — phase 실행 규칙, runner 동작, 커밋 컨벤션
- `docs/ARCHITECTURE.md` — 프로젝트 전체 컨텍스트 (이 phase 에서 docs 는 수정하지 않는다)

그리고 아래 4 개 workflow 파일을 직접 읽어 현재 사용 중인 action 버전을 모두 파악하라. 리팩토링은 source-first 다:

- `.github/workflows/news_collector.yml`
- `.github/workflows/news_collector_v2_active.yml`
- `.github/workflows/watchdog.yml`
- `.github/workflows/ci.yml`

이전 phase 산출물: 없음 (이 phase 가 Round 4 의 첫 phase).

참고: Round 3 phase 4 (`tasks/5-round3-cleanup/phase4.md`) 가 직전에 동일한 mechanical replace 패턴으로 `@v3 → @v4`, `@v4 → @v5` 를 수행했다. 이번 phase 는 그 패턴을 한 단계 위로 이어가는 것뿐이다. 작업 방식 참고용으로 그 phase 파일을 읽어도 좋다.

문서보다 코드(YAML)가 우선이다. 현재 베이스라인 줄 번호와 실제 파일이 어긋나면 줄 번호가 아니라 **버전 문자열**을 기준으로 치환하라.

## 작업 내용

`.github/workflows/` 하위의 4 개 파일에서 **정확히 두 종류의 줄만** in-place 치환하라.

| 파일 | 라인 (베이스라인) | before | after |
|---|---|---|---|
| `news_collector.yml` | L15 | `uses: actions/checkout@v4` | `uses: actions/checkout@v5` |
| `news_collector.yml` | L18 | `uses: actions/setup-python@v5` | `uses: actions/setup-python@v6` |
| `news_collector_v2_active.yml` | L16 | `uses: actions/checkout@v4` | `uses: actions/checkout@v5` |
| `news_collector_v2_active.yml` | L19 | `uses: actions/setup-python@v5` | `uses: actions/setup-python@v6` |
| `watchdog.yml` | L13 | `uses: actions/checkout@v4` | `uses: actions/checkout@v5` |
| `watchdog.yml` | L16 | `uses: actions/setup-python@v5` | `uses: actions/setup-python@v6` |
| `ci.yml` (gitleaks job) | L12 | `uses: actions/checkout@v4` | `uses: actions/checkout@v5` |
| `ci.yml` (python-test job) | L23 | `uses: actions/checkout@v4` | `uses: actions/checkout@v5` |
| `ci.yml` (python-test job) | L24 | `uses: actions/setup-python@v5` | `uses: actions/setup-python@v6` |
| `ci.yml` (web-test job) | L36 | `uses: actions/checkout@v4` | `uses: actions/checkout@v5` |

**총 변경량: 4 파일 / 10 줄 / in-place 치환 (+10 / −10 대칭).**

다른 줄은 **절대 수정하지 마라**. 들여쓰기, 따옴표 스타일, `with:` 옵션 (`python-version`, `fetch-depth`, `cache`, `cache-dependency-path` 등), `env:` 블록, `${{ secrets.* }}` 참조, `on:` 트리거, `schedule:`, `workflow_dispatch:`, job 이름, step 이름, `runs-on`, `timeout-minutes`, run 본문 모두 그대로 유지.

`actions/setup-node@v4` 와 `gitleaks/gitleaks-action@v2` 는 **건드리지 마라**. Round 4 scope 밖이다.

검증 도구로 `python3 -c "import yaml; ..."`, `pip install pyyaml`, 정규식 fallback 등을 동원하지 마라. 외부 패키지 설치, 네트워크 호출, 환경변수 의존 모두 금지. 검증은 아래 AC 의 grep + git diff 만으로 한다.

## Acceptance Criteria

```bash
# 1) 버전 문자열 카운트 — 정확히 일치해야 함
test "$(grep -r 'actions/checkout@v5'     .github/workflows | wc -l)" = "6"
test "$(grep -r 'actions/setup-python@v6' .github/workflows | wc -l)" = "4"
test "$(grep -r 'actions/checkout@v4'     .github/workflows | wc -l)" = "0"
test "$(grep -r 'actions/setup-python@v5' .github/workflows | wc -l)" = "0"

# 2) diff 형상: 정확히 4 파일 / +10 / −10 대칭
git diff --stat .github/workflows/
# 기대: " 4 files changed, 10 insertions(+), 10 deletions(-)"

# 3) 스코프 외 파일이 안 건드려졌는지.
#    단, tasks/6-round4-upgrades/index.json 은 phase status 갱신을 위해 허용.
unexpected="$(git diff --name-only -- web docs src tasks spec \
  | grep -v -x 'tasks/6-round4-upgrades/index.json')"
test -z "$unexpected"
```

## AC 검증 방법

위 명령들을 모두 실행하라. 4 개의 grep 카운트 검증과 1 개의 diff 형상 검증, 1 개의 스코프 가드가 모두 0 으로 종료해야 한다. 통과 시 `tasks/6-round4-upgrades/index.json` 의 phase 1 status 를 `"completed"` 로 변경하라.

수정 3 회 이상 시도해도 실패하면 status 를 `"error"` 로 변경하고, `"error_message"` 필드에 어떤 검증이 어떤 실제 카운트로 어긋났는지 기록한 뒤 중단하라.

작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 status 를 `"blocked"` 로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 즉시 중단하라.

## 주의사항

- **그 두 종류의 `uses:` 줄 외 어떤 것도 만지지 마라.** 들여쓰기, 따옴표, `with:` 하위 옵션, `env:`, `secrets.*`, `runs-on`, `schedule`, `workflow_dispatch`, job/step 이름, run 본문, comment, 빈 줄 모두 그대로.
- `actions/setup-node@v4` 는 의도적으로 scope 밖이다. 업그레이드 금지.
- `gitleaks/gitleaks-action@v2` 는 의도적으로 scope 밖이다. 업그레이드 금지.
- `python-version: '3.10'` 은 그대로 유지하라. 버전 변경 금지.
- YAML parse 검증을 위해 `pip install pyyaml` 하지 마라. 외부 패키지 설치 / 네트워크 호출 / 환경변수 의존 일체 금지.
- web/, docs/, src/, spec/, 다른 tasks/ 디렉토리는 건드리지 마라. AC 의 스코프 가드가 실패한다.
- 이 phase 는 workflow YAML 만 다룬다. `web/middleware.ts` 나 `docs/ARCHITECTURE.md` 는 다음 phase 에서 처리한다 — 미리 손대지 마라.
- runner 가 phase 종료 후 `cd web && npm run build` 를 자동 실행한다. 이 phase 는 web/ 코드를 건드리지 않으므로 베이스라인이 통과하던 상태라면 그대로 통과한다.
- 줄 번호는 베이스라인 기준 참고값이다. 실제 파일에서는 **버전 문자열을 anchor 로** 치환하라. 결과 카운트 (6/4/0/0) 가 핵심이다.
