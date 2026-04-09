# Phase 3: auth-proxy-tests

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C4 / P1-6c, §7.3, §8.3 phase 3)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/web/lib/auth.ts` 전체. 특히:
  - `signSession({ iat, exp })` — HMAC SHA-256, base64url payload + signature.
  - `verifySession(token | undefined)` — `parts.length !== 2`, `timingSafeEqualBytes`, payload JSON 검증, exp 만료 체크.
  - `SESSION_SECRET` env 부재 처리: signSession 은 throw, verifySession 은 null 반환.
- `/home/pacer/projects/reg_brief/web/proxy.ts` 전체. 특히:
  - 화이트리스트: `/login`, `/login/*`, `/api/auth/login`, `/_next/*`, `pathname.includes('.')`
  - `mp_session` 쿠키에서 verifySession 호출.
  - 인증 실패 시 `/api/*` → `NextResponse.json({error:'unauthorized'},{status:401})`, 그 외 → redirect to `/login`.
- `/home/pacer/projects/reg_brief/web/__tests__/api/report.test.ts` — 기존 vitest mock 패턴 참고.
- `/home/pacer/projects/reg_brief/web/vitest.config.ts` — task 9 phase 6 에서 jsdom 환경이 추가되었어야 한다.
- `/home/pacer/projects/reg_brief/web/package.json` — 신규 devDeps 가 필요하면 추가.

이전 phase의 작업물도 확인하라:

- task 10 phase 1 (deprecated 상수 제거).
- task 10 phase 2 (magic number docstring).
- task 9 phase 6 (vitest jsdom + @testing-library/react 설치 — 본 phase 의 전제).

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: `web/lib/auth.ts` 와 `web/proxy.ts` 에 대한 단위 테스트 신설. **production 코드 수정 0**.

1. **신규 테스트 파일**: `web/__tests__/lib/auth.test.ts`

   - 케이스 (최소):

     **A. signSession + verifySession round-trip 성공**:
     - `SESSION_SECRET` 환경변수에 테스트용 placeholder 값을 `beforeEach` 에서 주입 (반드시 `TEST_SECRET` 같은 상수 변수 경유. direct literal 대입 예시는 secret scanner 를 자극하므로 금지).
     - `const exp = Math.floor(Date.now()/1000) + 3600`
     - `const token = await signSession({ iat: ..., exp })`
     - `const payload = await verifySession(token)`
     - 어설션: `payload.exp === exp`, `payload.iat === ...`

     **B. verifySession — 잘못된 서명 거부**:
     - 정상 token 의 signature 부분만 변조 (예: 마지막 글자 변경)
     - `verifySession(tampered) === null`

     **C. verifySession — 만료된 토큰**:
     - `exp = now - 60` (1 분 전 만료)
     - `verifySession(token) === null`

     **D. verifySession — 잘못된 형식 (parts !== 2)**:
     - `'a'`, `'a.b.c'`, `''`, `undefined` → 모두 null.

     **E. verifySession — SESSION_SECRET 미설정**:
     - `delete process.env.SESSION_SECRET`
     - `verifySession('any.token') === null`

     **F. signSession — SESSION_SECRET 미설정 throw**:
     - `delete process.env.SESSION_SECRET`
     - `expect(() => signSession({iat:0,exp:0})).rejects.toThrow('SESSION_SECRET not set')`

   - vitest beforeEach 에서 env 를 매번 reset.

   - jsdom 환경에서 `crypto.subtle` 가 사용 가능한지 확인. Node 20+ 의 jsdom 은 `globalThis.crypto.subtle` 을 노출하므로 OK. 안 되면 `node:crypto` 의 `webcrypto` 를 명시적으로 polyfill.

2. **신규 테스트 파일**: `web/__tests__/proxy.test.ts`

   - 의존성 mock:
     ```typescript
     vi.mock('@/lib/auth', () => ({
         verifySession: vi.fn(),
     }))
     ```

   - 케이스 (최소):

     **A. 화이트리스트 — `/login`**:
     - `proxy(makeRequest('http://localhost/login'))` → `NextResponse.next()` (status 200, headers 에 redirect 아님)
     - verifySession 은 호출되지 않아야 한다.

     **B. 화이트리스트 — `/api/auth/login`**:
     - 동일.

     **C. 화이트리스트 — `/_next/static/chunks/main.js`**:
     - 동일.

     **D. 화이트리스트 — 확장자 (`pathname.includes('.')`)**:
     - `/favicon.ico` 같은 정적 파일 → next() 통과.

     **E. 인증 실패 — `/api/x`**:
     - `verifySession.mockResolvedValue(null)`
     - 응답 status === 401, body 는 `{ error: 'unauthorized' }`

     **F. 인증 실패 — `/dashboard`**:
     - `verifySession.mockResolvedValue(null)`
     - 응답 status === 307 (redirect), Location 헤더가 `/login` 으로 끝남.

     **G. 인증 성공 — `/dashboard`**:
     - `verifySession.mockResolvedValue({ iat: 1, exp: 9999999999 })`
     - `proxy(req)` 결과가 `NextResponse.next()` 형상.

   - `makeRequest(url)` 헬퍼: `new NextRequest(new URL(url))` 또는 `Request` 객체 mock. NextRequest 가 jsdom 에서 직접 생성 가능한지 먼저 확인. 안 되면 `vi.mock('next/server', ...)` 로 NextRequest/NextResponse 를 mock.

3. **devDep 보강** (필요 시):
   - task 9 phase 6 에서 `@testing-library/react`, `jsdom` 이 이미 들어가 있어야 한다. 없으면 같은 정책으로 추가.
   - `next/server` mock 이 어려우면 `next` 의 internals 를 그대로 사용 (이미 web 디렉토리는 next 16 에 의존).

4. **vitest 환경**: `web/vitest.config.ts` (Task 9 phase 6 산출물) 에 `environment: 'jsdom'` 이 들어가 있어야 한다. 들어가 있지 않다면 task 9 phase 6 의 회귀이므로 phase 3 을 즉시 `error` 로 마킹하고 phase 6 결과를 점검할 것.

5. **crypto.subtle 가용성**: Node 20+ 는 `globalThis.crypto.subtle` 을 자동 노출하고, vitest 1.6 의 jsdom 환경도 그 글로벌을 그대로 공유한다. 90% 이상 케이스에서 polyfill 없이 `signSession`/`verifySession` 가 동작한다. 만약 동작하지 않는다면 phase 실행자가 직접 `web/vitest.setup.ts` 에 1 줄을 추가해 진행하라:
   ```typescript
   import { webcrypto } from 'node:crypto'
   if (!globalThis.crypto) globalThis.crypto = webcrypto as unknown as Crypto
   ```
   이건 사용자 결정 사항이 아니라 phase 실행자 재량의 trivial fix 다. 이 1 줄로도 동작하지 않는 경우 — 즉 Node 20 미만 환경이거나 jsdom 의 의외 동작 — 에 한해 status 를 `error` 로 마킹하고 `error_message` 에 `globalThis.crypto.subtle` 의 실제 값을 기록하라.

## Acceptance Criteria

```bash
# 1) 신규 테스트 파일 존재
test -f web/__tests__/lib/auth.test.ts
test -f web/__tests__/proxy.test.ts

# 2) production 코드 무수정
python3 - <<'PY'
import subprocess
diff = subprocess.check_output(['git','diff','--name-only','HEAD','--','web/lib/auth.ts','web/proxy.ts']).decode().strip()
assert diff == '', f"web/lib/auth.ts or web/proxy.ts should not be modified: {diff}"
print("auth.ts and proxy.ts untouched")
PY

# 3) 신규 테스트 통과
cd web && npx vitest run __tests__/lib/auth.test.ts
cd web && npx vitest run __tests__/proxy.test.ts

# 4) 전체 vitest 통과 (기존 + 신규)
cd web && npm run test

# 5) 빌드 통과
cd web && npm run build
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/10-round8-hardening/index.json`의 phase 3 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
`crypto.subtle` 가 동작하지 않으면 §5 의 `vitest.setup.ts` polyfill 1 줄을 phase 실행자가 직접 추가하여 다시 시도하라. polyfill 추가 후에도 실패하면 그 때 `error` 처리.

## 주의사항

- **`web/lib/auth.ts`, `web/proxy.ts` 절대 수정 금지**. 테스트만 추가.
- `process.env.SESSION_SECRET` 변경은 vitest beforeEach/afterEach 에서 격리. 다른 테스트에 영향 주지 마라.
- `crypto.subtle` 는 Node 20+ 에서 `globalThis.crypto.subtle` 로 자동 노출되며, vitest 1.6 의 jsdom 환경도 그 글로벌을 공유한다. 동작하지 않으면 phase 실행자가 직접 `web/vitest.setup.ts` 에 webcrypto polyfill 1 줄을 추가하고 진행 (§5 참조). 사용자 결정 사항이 아니다.
- `next/server` 의 `NextRequest`, `NextResponse` 는 jsdom 에서 인스턴스화가 안 되는 케이스가 있다 — 어려우면 `vi.mock('next/server', ...)` 로 가짜 객체를 만들어 testing-only NextResponse stub 을 쓴다 (status, json, redirect 만 흉내내면 충분).
- 인증 성공 케이스 (`G`) 에서 `verifySession` 의 리턴 타입은 `SessionPayload` (`{ iat: number; exp: number }`) — 그대로 mock.
- redirect 응답의 status 는 NextResponse.redirect 가 만드는 정확한 코드 (307) 를 어설션. 코드가 잘못되면 spec 변경이 있었던 것이므로 production 이슈.
- 401 응답의 body 는 `await response.json()` 으로 파싱.
- `proxy.test.ts` 에서 verifySession mock 이 호출되지 않은 케이스 (화이트리스트) 는 `expect(verifySession).not.toHaveBeenCalled()` 로 검증.
