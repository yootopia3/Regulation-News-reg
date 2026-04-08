# Phase 3: docs/ARCHITECTURE.md 의 middleware.ts 표기 sync

## 사전 준비

먼저 아래 문서를 직접 읽어 현재 표기 상태와 문맥을 파악하라:

- `CLAUDE.md` — phase 실행 규칙
- `docs/ARCHITECTURE.md` — 특히 §2 (web 디렉토리 트리), §4.4 (Web Dashboard / Security), §4.5 (Authentication). `middleware.ts` 표기가 현재 정확히 3 곳 있는지 grep 으로 직접 재확인하라.

이전 phase 산출물:
- Phase 1: `.github/workflows/*.yml` action 버전 업그레이드. 이 phase 와 직접 관련 없음.
- Phase 2: `web/proxy.ts` 신규 생성, `web/middleware.ts` 삭제. **이 phase 의 표기 변경 근거**.

핵심 소스 파일:
- `web/proxy.ts` — Phase 2 의 결과물. 존재 여부와 함수명을 직접 확인.

문서보다 코드가 우선이다. 이 phase 는 코드 사실 (proxy.ts) 에 맞춰 docs 표기만 동기화한다.

## 작업 내용

`docs/ARCHITECTURE.md` 의 `middleware.ts` 표기 **3 곳**을 `proxy.ts` 로 patch 하라. 의미 변경은 일체 금지하며, 단순 표기 동기화다.

베이스라인 위치 (줄 번호는 현재 기준이며 변경 후에는 살짝 달라질 수 있음):

| 라인 | before (핵심 텍스트) | after |
|---|---|---|
| L95  | `└── middleware.ts           # Route protection (mp_session cookie guards /api/*)` | `└── proxy.ts                # Route protection (mp_session cookie guards /api/*)` — 파일명 뒤에 공백을 정확히 **5 글자** 더 넣어 `# Route protection` 의 시작 컬럼을 베이스라인과 동일하게 유지 |
| L162 | `**Security**: Protected by `middleware.ts` (Cookie-based Auth).` | `**Security**: Protected by `proxy.ts` (Cookie-based Auth).` |
| L177 | `보호 대상 route는 `middleware.ts` 가 동일 헬퍼를 사용해 검사한다.` | `보호 대상 route는 `proxy.ts` 가 동일 헬퍼를 사용해 검사한다.` |

다른 어떤 줄도 손대지 마라. `docs/MASTER_CONTEXT.md`, `docs/PRD.md`, `docs/REQUIREMENTS.md`, `docs/archive/**`, `spec/**`, `tasks/**` (단, `tasks/6-round4-upgrades/index.json` 의 phase status 갱신은 허용) 도 손대지 마라.

## Acceptance Criteria

```bash
# 1) 표기 sync 완료 — middleware 가 ARCHITECTURE.md 에 더 이상 없음
test "$(grep -c -i 'middleware' docs/ARCHITECTURE.md)" = "0"

# 2) proxy.ts 표기가 정확히 3 회 등장
test "$(grep -c 'proxy\.ts' docs/ARCHITECTURE.md)" = "3"

# 3) diff 형상: 1 파일, 3 줄 in-place 치환 (트리 정렬 보정 공백 포함)
git diff --stat docs/ARCHITECTURE.md
# 기대: " 1 file changed, 3 insertions(+), 3 deletions(-)"

# 4) Phase 2 결과가 여전히 살아있는지 sanity check
test -f web/proxy.ts
test ! -e web/middleware.ts

# 5) 스코프 외 파일이 안 건드려졌는지.
#    단, tasks/6-round4-upgrades/index.json 은 phase status 갱신을 위해 허용.
unexpected="$(git diff --name-only -- web src .github tasks spec \
    docs/MASTER_CONTEXT.md docs/PRD.md docs/REQUIREMENTS.md docs/archive \
  | grep -v -x 'tasks/6-round4-upgrades/index.json')"
test -z "$unexpected"
```

## AC 검증 방법

위 모든 명령이 0 으로 종료해야 한다. 통과 시 `tasks/6-round4-upgrades/index.json` 의 phase 3 status 를 `"completed"` 로 변경하라.

수정 3 회 이상 시도해도 실패하면 status 를 `"error"`, `"error_message"` 에 실패한 AC 와 현재 grep 카운트를 기록하고 중단하라.

작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 `"blocked"` + `"blocked_reason"` 으로 기록하고 즉시 중단하라.

## 주의사항

- `docs/MASTER_CONTEXT.md`, `docs/PRD.md`, `docs/REQUIREMENTS.md`, `docs/archive/**`, `spec/**`, `tasks/**` (phase status 갱신용 자기 자신 제외) 절대 수정 금지. Round 4 scope 밖이다.
- `docs/ARCHITECTURE.md` 의 다른 줄을 정리/리포맷/오탈자 수정/용어 통일하지 마라. 정확히 3 줄만 patch.
- L95 트리 정렬 공백을 마음대로 재정렬 금지 — `proxy.ts` (8 자) 가 `middleware.ts` (13 자) 보다 **5 글자** 짧다. 트리 다이어그램의 컬럼 정렬 (`# Route protection ...` 주석이 다른 줄과 같은 컬럼에 오도록) 을 유지하기 위해 파일명 뒤 공백을 정확히 **5 글자** 더 넣어 보정하라. 트리 구조 자체 (`└──` 들여쓰기, 부모/자식 관계) 는 변경 금지.
- 의미 변경 금지: 인증 동작 / 보호 대상 / 헬퍼 사용 방식에 관한 설명은 그대로.
- `web/proxy.ts` / `web/middleware.ts` / `.github/workflows/*.yml` 를 손대지 마라. 이 phase 는 docs only 다.
- runner 가 phase 종료 후 `cd web && npm run build` 를 자동 실행한다. 이 phase 는 web/ 코드 변경이 0 이므로 Phase 2 의 결과물이 그대로 빌드되어 통과해야 한다.
- `grep -c -i 'middleware'` 가 0 이 되지 않으면 patch 누락이다. 3 곳을 모두 잡았는지 다시 확인하라.
