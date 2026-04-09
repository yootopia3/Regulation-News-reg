# Phase 4: sidebar-extraction

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C3, §7.2, §8.2 phase 4, §9.2, §11 R3)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx` — phase 1–3 가 적용된 상태. 특히 L210–473 의 nested `Sidebar = () => (...)` 클로저. 클로저가 close-over 하는 외부 식별자를 전부 식별하라:
  - state: `isMenuOpen`, `isAgencyExpanded`, `isRegExpanded`, `isFSSRegGroupExpanded`, `isSanctionExpanded`, `currentCategory`, `selectedAgency`
  - setter: `setIsMenuOpen`, `setIsAgencyExpanded`, `setIsRegExpanded`, `setIsFSSRegGroupExpanded`, `setIsSanctionExpanded`, `setCurrentCategory`, `setSelectedAgency`
  - 계산값: `hasNewPress`, `hasNewReg`, `hasNewSanction` (phase 3 의 훅 결과)
  - 상수: `agencyOrder`, `agencyNames`, `regAgencyOrder`, `regAgencyNames`, `sanctionAgencyOrder`, `sanctionAgencyNames` (phase 1)
  - 컴포넌트: `<AgencyIcon />` (phase 2)
- `/home/pacer/projects/reg_brief/web/components/dashboard/constants.ts` (phase 1)
- `/home/pacer/projects/reg_brief/web/components/dashboard/AgencyIcon.tsx` (phase 2)
- `/home/pacer/projects/reg_brief/web/components/dashboard/useHasNewByCategory.ts` (phase 3)

이전 phase의 작업물도 확인하라:

- phase 1, 2, 3 의 산출물이 모두 적용되어 있어야 한다. 적용되지 않았다면 phase 4 를 진행하기 전에 status 를 `error` 로 마킹하고 사용자에게 보고.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: nested closure `Sidebar` 를 시블링 컴포넌트 파일로 분리. parent 의 state 와 setter 는 **전부 props 로 주입**. JSX 마크업은 한 글자도 바꾸지 마라.

1. **신규 파일**: `web/components/dashboard/Sidebar.tsx`
   - Props 인터페이스:
     ```typescript
     import React from 'react'
     import AgencyIcon from './AgencyIcon'
     import {
         agencyOrder,
         regAgencyOrder,
         sanctionAgencyOrder,
         agencyNames,
         regAgencyNames,
         sanctionAgencyNames,
         DashboardCategory,
     } from './constants'

     export type SidebarProps = {
         // Open/close
         isMenuOpen: boolean
         onCloseMenu: () => void

         // Selection state
         currentCategory: DashboardCategory
         selectedAgency: string | null

         // Selection handlers
         onSelectHome: () => void
         onSelectPress: (agency: string | null) => void
         onSelectReg: (agency: string | null) => void
         onSelectSanction: (agency: string | null) => void

         // Expansion state
         isAgencyExpanded: boolean
         isRegExpanded: boolean
         isFSSRegGroupExpanded: boolean
         isSanctionExpanded: boolean

         // Expansion toggles
         onToggleAgency: () => void
         onToggleReg: () => void
         onToggleFSSRegGroup: () => void
         onToggleSanction: () => void

         // NEW badges
         hasNewPress: boolean
         hasNewReg: boolean
         hasNewSanction: boolean
     }

     export default function Sidebar(props: SidebarProps): React.ReactElement {
         // ... destructure or use props.X directly
         return (
             <>
                 {/* Mobile Backdrop */}
                 ...
                 {/* Drawer */}
                 ...
             </>
         )
     }
     ```
   - 본문 JSX: nested closure 안의 `<>...<aside>...</aside></>` 마크업을 **그대로** 옮긴다. 다음 치환만 수행:
     - `isMenuOpen` → `props.isMenuOpen` 또는 destructure 변수
     - `setIsMenuOpen(false)` → `props.onCloseMenu()`
     - `setCurrentCategory('press_release'); setSelectedAgency(null)` → `props.onSelectHome()` 또는 `props.onSelectPress(null)` (홈 버튼은 전용 handler)
     - `setIsAgencyExpanded(!isAgencyExpanded); setCurrentCategory('press_release'); setSelectedAgency(null)` → `props.onToggleAgency()` (이 토글 핸들러는 expansion + selection 둘 다 처리)
     - `agencyOrder.map((code) => ...)` 안의 `setCurrentCategory('press_release'); setSelectedAgency(code)` → `props.onSelectPress(code)`
     - 동일 패턴으로 reg / sanction / FSSRegGroup
   - **마크업/스타일 변경 절대 금지**: className, gap, padding, gradient, transition-all, animate-pulse 같은 Tailwind 토큰 한 글자도 바꾸지 마라.
   - **2 단 FSS 메뉴** (`isFSSRegGroupExpanded`) 도 그대로 옮긴다.

2. **`DashboardV2.tsx` 수정**:
   - 상단 import 추가:
     ```typescript
     import Sidebar from './Sidebar'
     ```
   - L210–473 의 `const Sidebar = () => (...)` 클로저 **삭제**.
   - JSX 본문에서 `<Sidebar />` 호출을 props 전체 주입으로 교체:
     ```tsx
     <Sidebar
         isMenuOpen={isMenuOpen}
         onCloseMenu={() => setIsMenuOpen(false)}
         currentCategory={currentCategory}
         selectedAgency={selectedAgency}
         onSelectHome={() => {
             setCurrentCategory('press_release')
             setSelectedAgency(null)
         }}
         onSelectPress={(agency) => {
             setCurrentCategory('press_release')
             setSelectedAgency(agency)
         }}
         onSelectReg={(agency) => {
             setCurrentCategory('regulation_notice')
             setSelectedAgency(agency)
         }}
         onSelectSanction={(agency) => {
             setCurrentCategory('sanction_notice')
             setSelectedAgency(agency)
         }}
         isAgencyExpanded={isAgencyExpanded}
         isRegExpanded={isRegExpanded}
         isFSSRegGroupExpanded={isFSSRegGroupExpanded}
         isSanctionExpanded={isSanctionExpanded}
         onToggleAgency={() => {
             setIsAgencyExpanded(!isAgencyExpanded)
             setCurrentCategory('press_release')
             setSelectedAgency(null)
         }}
         onToggleReg={() => {
             setIsRegExpanded(!isRegExpanded)
             setCurrentCategory('regulation_notice')
             setSelectedAgency(null)
         }}
         onToggleFSSRegGroup={() => setIsFSSRegGroupExpanded(!isFSSRegGroupExpanded)}
         onToggleSanction={() => {
             setIsSanctionExpanded(!isSanctionExpanded)
             setCurrentCategory('sanction_notice')
             setSelectedAgency(null)
         }}
         hasNewPress={hasNewPress}
         hasNewReg={hasNewReg}
         hasNewSanction={hasNewSanction}
     />
     ```
   - 토글 핸들러의 사이드 이펙트 (expansion + currentCategory + selectedAgency) 는 원본과 1:1 동일.

3. **LOC 감소 검증**: phase 4 후 `DashboardV2.tsx` 가 **≤ 300 LOC** 가 되는지 확인 (원본 592 → ~250 정도 예상). roadmap §9.2 의 회귀 체크리스트가 ≤ 300 으로 못 박혀 있으므로 이 phase 의 AC 도 ≤ 300 으로 강제한다.

## Acceptance Criteria

```bash
# 1) 신규 파일 존재
test -f web/components/dashboard/Sidebar.tsx

# 2) Sidebar closure 가 사라졌는가
! grep -q "const Sidebar = () =>" web/components/dashboard/DashboardV2.tsx

# 3) Sidebar import 가 들어갔는가
grep -q "import Sidebar from './Sidebar'" web/components/dashboard/DashboardV2.tsx

# 4) 사용처가 props 주입 형태인가 (구체 prop 1개 grep 으로 확인)
grep -q "isMenuOpen={isMenuOpen}" web/components/dashboard/DashboardV2.tsx
grep -q "hasNewPress={hasNewPress}" web/components/dashboard/DashboardV2.tsx

# 5) DashboardV2 LOC 감소 (roadmap §9.2 와 동일한 임계값)
LOC=$(wc -l < web/components/dashboard/DashboardV2.tsx)
echo "DashboardV2.tsx LOC: $LOC"
test "$LOC" -le 300

# 6) 빌드 + 테스트 통과
cd web && npm run build
cd web && npm run test

# 7) Sidebar.tsx 가 외부 state 를 직접 import 하지 않는지 (props-only)
! grep -q "useState" web/components/dashboard/Sidebar.tsx
! grep -q "useEffect" web/components/dashboard/Sidebar.tsx
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/9-round7-dashboard-decomposition/index.json`의 phase 4 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
시각적 회귀가 의심되면 (예: 빌드는 통과하지만 사용자 수동 확인이 필요해 보이면) `blocked` 가 아닌 `completed` 처리하되 phase output 에 "manual visual check required" 를 남겨라.

## 주의사항

- **JSX 마크업/스타일/className 한 글자도 바꾸지 마라**. Sidebar 의 모양은 1 픽셀도 변하면 안 된다.
- **state 는 Sidebar 안에 만들지 마라**. `useState`, `useEffect`, `useMemo` 모두 금지 (parent 에서 주입).
- **2단 FSS 메뉴** 의 토글 (`isFSSRegGroupExpanded`) 는 currentCategory/selectedAgency 를 건드리지 않는다 — 단순 expansion 토글이다. 다른 토글들과 시그니처를 구분하라 (`onToggleFSSRegGroup` 만 사이드 이펙트 없음).
- 홈 버튼 (`설정` 위쪽 메뉴 항목) 은 `onSelectHome` 으로 분리. press 카테고리 + selectedAgency=null 로 가는 단일 동작.
- 토글 핸들러의 사이드 이펙트 (expansion 상태 + currentCategory + selectedAgency) 가 원본과 동일한지 1:1 매칭 확인. **expansion 토글 시 카테고리도 같이 바뀌는 것은 의도된 UX**.
- `selectedAgency` 의 타입은 `string | null` (literal union 아님). FSC_REG, FSS_REG, FSS_REG_INFO 같이 비-pressAgency 도 들어가므로 string.
- `Sidebar.tsx` 는 client component (`'use client'`) directive 가 필요할 수 있다 — handler / state 를 받지만 `useState` 는 안 쓴다. parent 가 client 면 child 도 자동으로 client 로 취급된다 (Next.js 16). 명시적으로 붙여도 무방.
- DashboardV2.tsx 가 300 LOC 를 초과하면 어떤 부분이 남아 있는지 grep 으로 점검 — 클로저 잔재 / 인라인 SVG / 상수 잔재가 있을 수 있다. roadmap §9.2 의 ≤ 300 임계값과 동일.
