# Phase 2: frontend-auth

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `CLAUDE.md` — phase 실행 규약 + 본 task의 commit/branch prefix.
- `tasks/3-auth-hardening/index.json` — task-level build_command. 본 phase의 build 검증은 `cd web && npm run build` 가 핵심.

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. **source-first** 다:

- `web/app/login/page.tsx` — 현재 클라이언트에서 `passcode === '1234'` 를 직접 비교(L15)하고, `document.cookie = "auth_token=valid; path=/; max-age=86400"` 으로 쿠키를 클라이언트가 set한다(L17).
- `web/middleware.ts` — 현재 matcher: `'/((?!api|_next/static|_next/image|favicon.ico).*)'` (L27). `api` 가 negative lookahead 안에 들어 있어 모든 `/api/*` 가 미들웨어 대상에서 빠진다. 쿠키 비교는 `authCookie.value !== 'valid'` 의 단순 문자열 비교(L19).
- `web/app/api/report/route.ts` — `/api/report` POST 핸들러. **본 phase에서 본문은 건드리지 않는다.** 미들웨어가 통과시킬 라이브 caller인 `web/components/ReportModal.tsx` 가 `fetch('/api/report', {method:'POST', ...})` 를 호출할 때 same-origin 기본 동작으로 쿠키를 자동 동봉하는지 재확인.
- `web/app/api/trigger-collect/route.ts` — POST 핸들러. **본문 변경 금지.** 미들웨어 보호만으로 충분.
- `web/app/api/check-collection-status/route.ts` — GET 핸들러. **본문 변경 금지.** 미들웨어 보호만으로 충분.
- `web/components/ReportModal.tsx` — `'use client'` 컴포넌트. L35의 `fetch('/api/report', ...)` 호출에 `credentials` 옵션이 없음을 재확인. same-origin 기본값으로 쿠키 자동 전송이라 본 phase의 인증 가드 추가 후에도 동작에 영향이 없어야 한다.
- `web/package.json` — 현재 dependencies에 `jose`, `jsonwebtoken`, `iron-session` 등 인증 라이브러리가 0건임을 재확인. 본 phase는 **새 dependency 추가 0건** 으로 간다.

이전 phase 산출물:

- `tasks/3-auth-hardening/phase1.md` 결과(백엔드 hygiene). 본 phase는 백엔드를 건드리지 않으나, build_command가 백엔드 import smoke를 포함하므로 phase 1이 깨졌다면 본 phase의 build 단계도 막힌다.

문서보다 코드가 우선이다.

## 작업 내용

본 phase는 단일 atomic 변경이다. 중간 상태에서는 로그인이 깨지므로 아래 4개 변경을 한 phase 안에서 모두 끝낸다.

### 1. Edge-compatible 서명 유틸 신설

새 파일 생성: `web/lib/auth.ts`

- 의도: Edge runtime(Next.js middleware 기본 실행 환경)에서 검증 가능한 dependency-free 서명 방식 제공. **`jose`/`jsonwebtoken`/`iron-session` 같은 새 npm dependency를 추가하지 마라.** Node `crypto` 모듈도 사용 금지(Edge 비호환).
- 서명 알고리즘: HMAC-SHA256 via `crypto.subtle.importKey` + `crypto.subtle.sign`. Web Crypto API 만 사용.
- secret 소스: `process.env.SESSION_SECRET`. 미설정이면 sign은 throw, verify는 항상 `null` 반환.
- 토큰 형식: `<base64url(payload-json)>.<base64url(hmac-bytes)>`. 두 segment.
- payload 형식: `{ "iat": <epoch_sec>, "exp": <epoch_sec + 86400> }`. 다른 필드 추가 금지.
- 시그니처 (TypeScript):
  ```ts
  export type SessionPayload = { iat: number; exp: number };
  export async function signSession(payload: SessionPayload): Promise<string>;
  export async function verifySession(token: string | undefined): Promise<SessionPayload | null>;
  ```
- 검증 로직 요구사항:
  - token이 undefined/빈 문자열/segment 분리 실패 → `null`.
  - HMAC 재계산 후 timing-safe 비교(자릿수 동일 + XOR 누적 후 0 비교; 라이브러리 사용 금지).
  - payload 디코드 실패 → `null`.
  - `payload.exp <= Math.floor(Date.now()/1000)` → `null`.
  - 모두 통과 → payload 반환.
- 본 모듈은 Node.js API를 import하지 마라. `crypto.subtle`, `TextEncoder`, `TextDecoder`, `atob`/`btoa` 는 Edge에서 사용 가능.

### 2. `/api/auth/login` route 신설

새 파일 생성: `web/app/api/auth/login/route.ts`

- POST 핸들러. body 형식: `{ passcode: string }`.
- 환경변수 둘 다 필요: `process.env.APP_PASSCODE`, `process.env.SESSION_SECRET`. 둘 중 하나라도 미설정이면 500 + `{ ok: false, error: "auth not configured" }` + `console.error("[/api/auth/login] APP_PASSCODE or SESSION_SECRET not set")`.
- passcode 비교: timing-safe(문자 단위 XOR 누적 후 0 비교, 길이 다르면 즉시 mismatch로 처리하되 동일한 작업량을 거치도록 padding).
- 일치 시:
  - `signSession({ iat: now, exp: now + 86400 })` 호출.
  - 응답 헤더에 `Set-Cookie: mp_session=<token>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=86400` 포함. Next의 `cookies().set(...)` 또는 `NextResponse` 의 `cookies.set` API 사용. 직접 헤더 문자열을 빌드해도 무방.
  - body: `{ ok: true }`, status 200.
- 불일치 시: 401 + `{ ok: false }` (메시지 본문에 비밀 노출 금지).
- runtime 명시: 본 route는 Node runtime/Edge runtime 어느 쪽이든 동작해야 한다. 단, Web Crypto만 쓰므로 Edge runtime이 더 일관적이다. 특별한 `export const runtime = 'edge'` 선언은 필수가 아니지만, 추가해도 무방.

### 3. `web/middleware.ts` 재작성

기존 파일 교체:

- matcher 변경: `['/((?!_next/static|_next/image|favicon.ico).*)']` — **`api` 를 negative lookahead 에서 제거**. 이로써 모든 `/api/*` 가 미들웨어 대상에 들어온다.
- 함수 본문에서 화이트리스트(인증 검증을 건너뛸 경로) 처리:
  - `pathname === '/login'` 또는 `pathname.startsWith('/login/')` → `NextResponse.next()`
  - `pathname === '/api/auth/login'` → `NextResponse.next()`
  - `pathname.startsWith('/_next')` → `NextResponse.next()`
  - `pathname.includes('.')` (favicon, public 정적 파일) → `NextResponse.next()`
- 화이트리스트가 아닌 경우:
  - `mp_session` 쿠키를 읽고 `verifySession(...)` 호출(`web/lib/auth.ts` 에서 import).
  - 검증 실패 시:
    - 경로가 `/api/` 로 시작하면 → `NextResponse.json({ error: 'unauthorized' }, { status: 401 })`
    - 그 외(페이지) → `NextResponse.redirect(new URL('/login', request.url))`
  - 검증 성공 시 → `NextResponse.next()`
- 기존 `auth_token` 쿠키 비교 로직(L19)은 완전히 제거. 새 `mp_session` 으로만 동작.
- 본 미들웨어는 Edge runtime에서 동작한다. Node `crypto` import 금지.

### 4. `web/app/login/page.tsx` 재작성

기존 파일 교체:

- L15-23 의 `handleLogin` 을 다음과 같이 바꾼다:
  - `e.preventDefault()` 호출 후 `await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ passcode }) })`.
  - 응답 ok면 `router.push('/')` + `router.refresh()`.
  - status 401이면 `setError('Invalid Passcode')`.
  - status 500이면 `setError('Authentication is not configured. Contact administrator.')`.
- `document.cookie = ...` 라인(L17) 완전 제거.
- hardcoded `'1234'` 비교(L15) 완전 제거.
- **UI 카피/필드/스타일은 변경 금지**(`<h1>MarketPulse-Reg 🔒</h1>`, placeholder `••••••••`, 버튼 라벨 `Access Dashboard` 등 모두 그대로).
- `'use client'` 디렉티브, `useState`/`useRouter` import는 그대로 유지.
- 입력 중 로딩 상태가 필요하면 추가 가능(필수 아님). 추가하더라도 button label 텍스트는 변경 금지.

## Acceptance Criteria

```bash
# 1. 새 파일 존재
test -f web/lib/auth.ts
test -f web/app/api/auth/login/route.ts

# 2. 클라이언트 하드코딩 passcode 잔존 0건
test -z "$(grep -n \"'1234'\" web/app/login/page.tsx)"

# 3. 클라이언트 쿠키 set 잔존 0건
test -z "$(grep -n 'document.cookie' web/app/login/page.tsx)"

# 4. middleware 가 api 를 negative lookahead 에서 제외하지 않음 (negative lookahead 안에 'api' 가 없어야 함)
test -z "$(grep -n '(?!api' web/middleware.ts)"

# 5. middleware 가 mp_session 쿠키를 검증함
grep -q 'mp_session' web/middleware.ts

# 6. middleware 가 /api/auth/login 을 화이트리스트로 통과시킴
grep -q '/api/auth/login' web/middleware.ts

# 7. middleware 가 /login 페이지를 화이트리스트로 통과시킴 (리다이렉트 루프 방지)
grep -qE "pathname === '/login'|pathname.startsWith\('/login/'\)" web/middleware.ts

# 8. /api/auth/login route 가 APP_PASSCODE 와 SESSION_SECRET 두 환경변수를 모두 참조함
grep -q 'APP_PASSCODE' web/app/api/auth/login/route.ts
grep -rq 'SESSION_SECRET' web/app/api/auth/login/route.ts web/lib/auth.ts

# 9. /api/auth/login 응답이 mp_session 쿠키를 HttpOnly 속성으로 set 함
grep -q 'mp_session' web/app/api/auth/login/route.ts
grep -qiE 'httponly|HttpOnly' web/app/api/auth/login/route.ts

# 10. Edge 비호환 Node crypto import 0건 (모든 흔한 형태 차단)
test -z "$(grep -rnE \"from ['\\\"](node:)?crypto['\\\"]\" web/middleware.ts web/lib/auth.ts web/app/api/auth/)"
test -z "$(grep -rnE \"require\\(['\\\"](node:)?crypto['\\\"]\\)\" web/middleware.ts web/lib/auth.ts web/app/api/auth/)"
test -z "$(grep -rnE \"import .* from ['\\\"](node:)?crypto['\\\"]\" web/middleware.ts web/lib/auth.ts web/app/api/auth/)"

# 11. package.json / package-lock.json diff 0줄 (의존성 추가 없음)
git diff --quiet web/package.json
git diff --quiet web/package-lock.json

# 12. task 단위 build_command 통과
venv/bin/python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer" && cd web && npm run build
```

## AC 검증 방법

위 12개 커맨드를 순서대로 직접 실행하라. 모두 통과하면 `tasks/3-auth-hardening/index.json` 의 phase 2 status를 `"completed"` 로 변경하라.

수정 3회 이상 시도해도 실패하면 status를 `"error"` 로, `error_message` 에 어느 단계 어떤 출력으로 실패했는지 기록하라.

다음 상황은 즉시 `"blocked"` 로 처리하고 `blocked_reason` 에 사유를 기록하라:

- `web/node_modules/` 가 존재하지 않거나 `next` 바이너리가 설치되지 않아 `cd web && npm run build` 가 환경 사유로 실패할 때(`next: not found`, `MODULE_NOT_FOUND` 등). 사용자가 사전에 `cd web && npm install` 을 1회 수동 수행해야 한다.
- `venv/` 가 존재하지 않거나 백엔드 dependencies(`pip install -r requirements.txt`)가 미설치되어 import smoke 가 환경 사유로 실패할 때.
- `APP_PASSCODE` 또는 `SESSION_SECRET` 환경변수가 로컬 dev `.env`/`.env.local` 어디에도 정의되어 있지 않고, 사용자가 추가할 권한 여부를 알 수 없을 때(빌드 자체는 통과할 수 있으나 phase 의도가 검증 불가능).
- `web/package.json` 또는 `web/package-lock.json` 에 dependency 추가가 강제되는 상황이 발생할 때(예: Web Crypto 만으로 구현이 불가능하다고 판단되는 경우 — 실제로는 가능하므로 발생하면 안 됨).
- Next.js 16의 미들웨어/Edge runtime API 변경으로 본 phase의 시그니처가 동작하지 않을 때.

## 주의사항

- **새 npm dependency 0건**. `package.json` / `package-lock.json` 변경 금지. `jose`, `jsonwebtoken`, `iron-session`, `cookie`, `cookies-next` 등 어떤 인증/쿠키 라이브러리도 추가하지 마라.
- **Node `crypto` 모듈 사용 금지**. Edge runtime 비호환. `crypto.subtle` (Web Crypto)만 사용.
- `web/app/api/report/route.ts`, `web/app/api/trigger-collect/route.ts`, `web/app/api/check-collection-status/route.ts` 의 **핸들러 본문을 건드리지 마라**. 인증은 미들웨어 한 곳에서만 처리한다.
- `web/components/ReportModal.tsx` 의 fetch 옵션을 변경하지 마라. same-origin fetch는 `credentials: 'include'` 옵션 없이도 쿠키를 자동 전송한다.
- `/api/auth/logout` route를 **추가하지 마라**. 본 라운드의 명시적 out-of-scope.
- `web/app/login/page.tsx` 의 UI 카피/필드/스타일 변경 금지. handleLogin 로직만 교체.
- `web/utils/supabase/client.ts` 의 placeholder fallback을 건드리지 마라(out-of-scope).
- `web/components/Dashboard.tsx` 는 phase 4에서 처리한다. 본 phase에서 삭제하지 마라.
- Supabase Auth, 외부 OAuth, 이메일 매직링크 등 인증 체계 교체 금지.
- 본 phase에서 백엔드(`src/`), DB(`db/`), 문서(`docs/`, `README.md`), `spec/`, `_runner/` 를 수정하지 마라.
- 기존 dashboard/searchbar/모달 컴포넌트의 동작 흐름을 깨지 마라.
