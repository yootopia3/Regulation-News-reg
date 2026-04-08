# Phase 2: web/middleware.ts → web/proxy.ts atomic rename

## 사전 준비

먼저 아래 문서를 읽어 web 인증/프록시 설계 의도를 파악하라:

- `CLAUDE.md` — phase 실행 규칙, runner 동작
- `docs/ARCHITECTURE.md` §2 (web 디렉토리 트리), §4.4 (Web Dashboard / Security), §4.5 (Authentication)

이 phase 에서 docs 는 수정하지 않는다. docs 표기 sync 는 Phase 3 에서 처리한다.

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작과 의존 관계를 파악하라. 리팩토링은 source-first 다:

- `web/middleware.ts` — **이 phase 에서 사라지는 파일.** 함수 본문 / 화이트리스트 / 쿠키 / matcher / 응답 동작을 1:1 보존하는 것이 핵심.
- `web/lib/auth.ts` — `verifySession` 의 시그니처와 동작. 이 phase 에서 수정 금지.
- `web/package.json` — `next: 16.1.0` 확인 (Next.js 16 proxy file convention 적용 대상).
- `web/next.config.ts` — middleware/proxy 경로를 직접 참조하지 않는지 확인 (베이스라인은 빈 config).
- `web/__tests__/` — middleware 를 import 하는 테스트가 있는지 grep 으로 확인 (베이스라인은 0 건).

이전 phase (Phase 1) 산출물:
- `.github/workflows/*.yml` 4 개 파일에서 `actions/checkout@v4 → @v5`, `actions/setup-python@v5 → @v6` 변경. 이 phase 와는 직접 관련 없다.

문서보다 코드가 우선이다.

## 작업 내용

Next.js 16 의 proxy file convention 으로 전환한다. **rename + 함수명 변경 + 옛 파일 삭제를 같은 phase 안에서 atomic 하게** 수행하라. 두 파일이 동시에 존재하는 중간 상태를 만들지 마라 — Next.js 16 에서 빌드 충돌/경고가 발생할 수 있다.

### 1. 새 파일 생성: `web/proxy.ts`

`web/middleware.ts` 의 내용을 그대로 옮기되, **함수명만** `middleware` → `proxy` 로 변경한다. 시그니처 / 본문 / 화이트리스트 / 쿠키 / 응답 동작은 bit-for-bit 동일.

```ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { verifySession } from '@/lib/auth'

const SESSION_COOKIE_NAME = 'mp_session'

export async function proxy(request: NextRequest) {
    // ... 기존 middleware 함수 본문 1:1 동일 ...
}

export const config = {
    matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
```

다음 항목은 **bit-for-bit 동일**해야 한다:
- `next/server` import (`NextResponse` 값 import + `NextRequest` 타입 import)
- `verifySession` import 경로 (`@/lib/auth`)
- `SESSION_COOKIE_NAME = 'mp_session'` 상수 (이름·값·위치 동일, 리터럴로 인라인 금지)
- 화이트리스트 5 조건: `pathname === '/login'`, `pathname.startsWith('/login/')`, `pathname === '/api/auth/login'`, `pathname.startsWith('/_next')`, `pathname.includes('.')`
- 인증 분기: 화이트리스트면 `NextResponse.next()`, 아니면 `request.cookies.get(SESSION_COOKIE_NAME)` → `verifySession(...)` 호출
- 인증 실패 시: `/api/` prefix 면 `NextResponse.json({ error: 'unauthorized' }, { status: 401 })`, 그 외엔 `NextResponse.redirect(new URL('/login', request.url))`
- 인증 성공 시: `NextResponse.next()`
- `export const config = { matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'] }`

### 2. 옛 파일 삭제: `web/middleware.ts`

같은 phase 안에서 삭제하라. 두 파일이 공존하는 커밋이 만들어지지 않도록 한 번에 처리.

### 3. 다른 파일은 손대지 마라

- `web/next.config.ts`, `web/lib/auth.ts`, `web/components/`, `web/app/`, `web/__tests__/`, `web/eslint.config.mjs`, `web/tsconfig.json` 등은 일절 수정하지 마라.
- import 경로를 통해 middleware 를 참조하는 다른 파일이 새로 생기지 않았는지 grep 으로 재확인하라 (베이스라인 0 건).

## Acceptance Criteria

```bash
# 1) 파일 형상
test -f web/proxy.ts
test ! -e web/middleware.ts

# 2) 함수명 변환
grep -q 'export async function proxy' web/proxy.ts
! grep -q 'export async function middleware' web/proxy.ts

# 3) 인증 로직 / 쿠키 / 화이트리스트 / matcher 1:1 보존
grep -q "SESSION_COOKIE_NAME = 'mp_session'"                       web/proxy.ts
grep -q "verifySession"                                            web/proxy.ts
grep -q "/api/auth/login"                                          web/proxy.ts
grep -q "pathname.startsWith('/_next')"                            web/proxy.ts
grep -q "pathname.includes('.')"                                   web/proxy.ts
grep -q "NextResponse.json({ error: 'unauthorized' }, { status: 401 })" web/proxy.ts
grep -q "NextResponse.redirect(new URL('/login', request.url))"    web/proxy.ts
grep -q "_next/static|_next/image|favicon.ico"                     web/proxy.ts

# 4) 다른 web 파일에서 middleware import 가 새로 생기지 않았는지
! grep -rn "from '@/middleware'"   web/app web/components web/lib web/__tests__ 2>/dev/null
! grep -rn "from './middleware'"   web/app web/components web/lib web/__tests__ 2>/dev/null

# 5) 빌드 + 테스트
cd web && npm run build
cd web && npm test
```

## AC 검증 방법

위 모든 명령이 0 으로 종료해야 한다. `npm run build` 와 `npm test` 가 통과해야 한다. 모두 통과 시 `tasks/6-round4-upgrades/index.json` 의 phase 2 status 를 `"completed"` 로 변경하라.

수정 3 회 이상 시도해도 실패하면 status 를 `"error"`, `"error_message"` 에 어떤 AC 가 실패했는지 + 빌드/테스트 출력 핵심을 기록하고 중단하라.

작업 중 사용자 개입이 반드시 필요한 상황 (예: 로컬 환경에서 `npm` 미설치, `node_modules` 손상 등) 이 발생하면 `"blocked"` + `"blocked_reason"` 으로 기록하고 즉시 중단하라.

## 주의사항

- **`middleware` → `proxy` 외에는 단 한 글자도 의미 있게 바꾸지 마라.** 화이트리스트 항목, 쿠키 이름, matcher 패턴, 응답 본문, redirect URL 빌드 방식 모두 그대로.
- `web/middleware.ts` 와 `web/proxy.ts` 가 동시에 존재하는 중간 상태를 만들지 마라. atomic rename 이 핵심이다.
- 화이트리스트 5 항목 (`/login` 정확 일치, `/login/` prefix, `/api/auth/login` 정확 일치, `/_next` prefix, `pathname.includes('.')`) 을 한 항목도 빠뜨리거나 추가하지 마라. 순서도 그대로.
- `SESSION_COOKIE_NAME` 상수를 제거하거나 다른 모듈로 옮기지 마라. 리터럴로 인라인하지 마라. (Round 4 scope 가 아니다.)
- `verifySession` 의 시그니처·호출 방식·import 경로를 바꾸지 마라.
- 401 응답 본문 `{ error: 'unauthorized' }` 와 status 401 을 변경하지 마라.
- `/login` redirect 의 URL 빌드 방식 (`new URL('/login', request.url)`) 을 변경하지 마라.
- `next/server` import 경로를 바꾸지 마라.
- 새 옵션 / 새 export / 새 import 를 추가하지 마라.
- `web/lib/auth.ts`, `web/next.config.ts`, `web/eslint.config.mjs`, `web/tsconfig.json`, `web/__tests__/**`, `web/app/**`, `web/components/**` 를 손대지 마라.
- `setup-node@v4` 가 ci.yml 에 있어도 건드리지 마라 (Round 4 scope 밖, Phase 1 과 동일 원칙).
- Round 4 의 다른 phase (Phase 1 의 workflow, Phase 3 의 docs) 작업을 이 phase 에서 동시에 수행하지 마라.
- `cd web && npm test` 는 vitest 다. 베이스라인 테스트가 깨지면 동작 보존이 안 되었다는 신호다 — 함수 본문을 다시 검토하라.
