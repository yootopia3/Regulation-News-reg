# Phase 1: constants-extraction

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C3, §7.2, §8.2 phase 1, §9.2)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx` 전체. 특히 L14–208 범위의 인라인 상수들:
  - L15: `pressAgencies = ['MOEF', 'FSC', 'FSS', 'BOK']`
  - L16: `regulationAgencies = ['FSC_REG', 'FSS_REG', 'FSS_REG_INFO']`
  - L17: `sanctionAgencies = ['FSS_SANCTION', 'FSS_MGMT_NOTICE']`
  - L174–180: `agencyOrder = pressAgencies`, `agencyNames: Record<string, string>`
  - L183–188: `regAgencyOrder`, `regAgencyNames`
  - L191–195: `sanctionAgencyOrder`, `sanctionAgencyNames`
  - L198–208: `agencyIcons: Record<string, React.ReactNode>` — **phase 1 에서는 손대지 마라** (phase 2 의 몫).
- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx` (Article 타입 정의가 있는 파일)
- `/home/pacer/projects/reg_brief/web/tsconfig.json` (import alias `@/` 확인)

이전 phase의 작업물도 확인하라:

- 본 phase 가 task 9 의 첫 phase 다. 이전 phase 산출물은 없음.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: **상수만** 별도 파일로 이동. 컴포넌트 / 아이콘 / 훅은 이 phase 에서 건드리지 마라.

1. **신규 파일**: `web/components/dashboard/constants.ts`
   - 아래 내용을 `DashboardV2.tsx` 에서 그대로 복사-이동:
     ```typescript
     // Category codes used throughout the dashboard sidebar/feed.
     export const pressAgencies = ['MOEF', 'FSC', 'FSS', 'BOK'] as const
     export const regulationAgencies = ['FSC_REG', 'FSS_REG', 'FSS_REG_INFO'] as const
     export const sanctionAgencies = ['FSS_SANCTION', 'FSS_MGMT_NOTICE'] as const

     // Order arrays — kept as aliases to the base tuples to preserve callsite
     // semantics ("which list to iterate in which section").
     export const agencyOrder = pressAgencies
     export const regAgencyOrder = regulationAgencies
     export const sanctionAgencyOrder = sanctionAgencies

     export const agencyNames: Record<string, string> = {
       'MOEF': '기획재정부',
       'FSC': '금융위원회',
       'FSS': '금융감독원',
       'BOK': '한국은행',
     }

     export const regAgencyNames: Record<string, string> = {
       'FSC_REG': '금융위원회',
       'FSS_REG': '금감원 - 세칙 제개정 예고',
       'FSS_REG_INFO': '금감원 - 최근 제개정 정보',
     }

     export const sanctionAgencyNames: Record<string, string> = {
       'FSS_SANCTION': '검사결과 제재',
       'FSS_MGMT_NOTICE': '경영유의사항',
     }

     export type DashboardCategory = 'press_release' | 'regulation_notice' | 'sanction_notice'
     ```
   - **값 하나도 바꾸지 마라**. 공백, 문자, 순서 전부 원본과 동일.
   - `DashboardCategory` 타입 alias 는 **`constants.ts` 안에 반드시 export 한다** (이후 phase 4 의 `Sidebar.tsx` props 타입에서 재사용). 단, `DashboardV2.tsx` 안의 `useState<'press_release' | 'regulation_notice' | 'sanction_notice'>` 호출부를 `useState<DashboardCategory>` 로 교체하는 것은 phase 실행자 재량이다 — TypeScript strict 빌드에서 컴파일 충돌이 나면 원본 리터럴 union 을 그대로 유지하라. 즉 alias export 는 mandatory, 사용처 교체는 conditional.

2. **`DashboardV2.tsx` 수정**:
   - 상단 import 에 추가:
     ```typescript
     import {
         pressAgencies,
         regulationAgencies,
         sanctionAgencies,
         agencyOrder,
         regAgencyOrder,
         sanctionAgencyOrder,
         agencyNames,
         regAgencyNames,
         sanctionAgencyNames,
         DashboardCategory,
     } from './constants'
     ```
   - 함수 본체 내 L15–17, L174–195 의 인라인 상수 선언을 삭제.
   - `useState<'press_release' | 'regulation_notice' | 'sanction_notice'>` 를 `useState<DashboardCategory>` 로 치환 (선택, 단 타입 불일치 나오면 원본 리터럴 유지).
   - `agencyIcons` (L198–208) 는 **건드리지 마라**.
   - Sidebar closure (L212+) 는 **건드리지 마라**.

3. **값 동일성 보증**:
   - `npm run build` 를 돌린 뒤 번들 사이즈 / 실행 동작이 변해서는 안 된다.
   - `npm run test` 의 기존 테스트 (`web/__tests__/api/report.test.ts`) 가 그대로 통과해야 한다.

## Acceptance Criteria

```bash
# 1) 신규 파일 존재
test -f web/components/dashboard/constants.ts

# 2) 인라인 상수 선언이 DashboardV2.tsx 에서 사라졌는가
! grep -q "const pressAgencies = \[" web/components/dashboard/DashboardV2.tsx
! grep -q "const regulationAgencies = \[" web/components/dashboard/DashboardV2.tsx
! grep -q "const sanctionAgencies = \[" web/components/dashboard/DashboardV2.tsx
! grep -q "const agencyNames: Record" web/components/dashboard/DashboardV2.tsx
! grep -q "const regAgencyNames: Record" web/components/dashboard/DashboardV2.tsx
! grep -q "const sanctionAgencyNames: Record" web/components/dashboard/DashboardV2.tsx

# 3) import 가 들어갔는가
grep -q "from './constants'" web/components/dashboard/DashboardV2.tsx

# 4) agencyIcons 는 그대로인가 (phase 1 에서 건드리면 안 됨)
grep -q "agencyIcons" web/components/dashboard/DashboardV2.tsx

# 5) Sidebar closure 는 그대로인가
grep -q "const Sidebar = () =>" web/components/dashboard/DashboardV2.tsx

# 6) 빌드 + 테스트 통과
cd web && npm run build
cd web && npm run test
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/9-round7-dashboard-decomposition/index.json`의 phase 1 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **값 변경 금지**. 공백, 따옴표, 배열 순서, 객체 키 순서 전부 원본과 일치해야 한다.
- **scope 최소화**: phase 1 은 상수 이동뿐이다. `agencyIcons`, `hasNewPress`, `Sidebar closure`, `as any` 캐스트 — 전부 다른 phase 의 몫.
- `DashboardCategory` 타입 alias 는 선택. 컴파일 에러가 나면 DashboardV2.tsx 안의 리터럴 유니언을 그대로 유지해도 된다.
- `constants.ts` 는 `.ts` 로 만든다 (`.tsx` 아님 — JSX 없음).
- 기존 `NewsCard.tsx`, `DateSection.tsx`, `Header.tsx`, `SearchBar.tsx` 등 다른 dashboard 컴포넌트 파일 수정 금지.
- `@/components/dashboard/constants` 경로를 쓸지 `./constants` 를 쓸지: 같은 디렉토리 안이므로 **상대 경로 (`./constants`)** 로 통일.
