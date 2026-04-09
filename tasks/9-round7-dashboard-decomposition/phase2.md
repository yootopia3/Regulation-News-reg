# Phase 2: agency-icon-component

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§7.2, §8.2 phase 2, §9.2)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx` — **phase 1 이후 상태**. 특히 L198–208 의 `agencyIcons: Record<string, React.ReactNode>` 와 L212 이후 sidebar closure 에서 `agencyIcons[code]` 를 호출하는 모든 지점.
- `/home/pacer/projects/reg_brief/web/components/dashboard/constants.ts` (phase 1 산출물)

이전 phase의 작업물도 확인하라:

- `web/components/dashboard/constants.ts` (phase 1)
- phase 1 에서 수정된 `DashboardV2.tsx` (상수 import 가 들어간 상태)

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: 10개의 agency SVG 를 별도 함수 컴포넌트로 분리. `DashboardV2.tsx` 안의 `agencyIcons` record 를 제거하고 호출부를 `<AgencyIcon code={code} />` 로 교체.

1. **신규 파일**: `web/components/dashboard/AgencyIcon.tsx`
   - 시그니처:
     ```typescript
     import React from 'react'

     type AgencyIconProps = {
         code: string
         className?: string
     }

     export default function AgencyIcon({ code, className = 'w-5 h-5' }: AgencyIconProps): React.ReactElement | null {
         switch (code) {
             case 'MOEF':
                 return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">...</svg>)
             case 'FSC':
                 return (...)
             // ... 나머지 8개
             default:
                 return null
         }
     }
     ```
   - 원본 SVG 마크업을 **한 글자도 바꾸지 말고** 복사. 특히:
     - `strokeLinecap`, `strokeLinejoin`, `strokeWidth={1.5}`, `viewBox="0 0 24 24"` 등 속성 전부 동일.
     - `className` 만 prop 으로 주입되도록 변경 (원본은 `className="w-5 h-5"` 하드코딩).
     - 여러 `<path>` 가 있는 케이스 (FSC, FSS_SANCTION 등) 전부 동일하게 이동.
   - 10개 케이스: `MOEF`, `FSC`, `FSS`, `BOK`, `FSC_REG`, `FSS_REG`, `FSS_REG_INFO`, `FSS_SANCTION`, `FSS_MGMT_NOTICE`. 빠뜨리면 sidebar 렌더 시 아이콘이 사라진다.
   - `default` 케이스는 `null` 반환 (unknown code 면 아이콘 미표시; 원본도 record 에 없으면 undefined → React 무시).

2. **`DashboardV2.tsx` 수정**:
   - 상단 import 추가:
     ```typescript
     import AgencyIcon from './AgencyIcon'
     ```
   - L198–208 의 `agencyIcons` record 선언 **삭제**.
   - 본문에서 `agencyIcons[code]` 를 사용하는 모든 지점을 `<AgencyIcon code={code} />` 로 교체. 검색 대상:
     - `{agencyIcons[code]}` (map iteration 내부)
     - `{agencyIcons['FSC_REG']}` (명시적)
     - `{agencyIcons['FSS']}` (명시적)
     - `{agencyIcons['FSS_REG']}`, `{agencyIcons['FSS_REG_INFO']}`
     - `{agencyIcons[code]}` (sanction map)
   - 교체 규칙:
     - `{agencyIcons[code]}` → `<AgencyIcon code={code} />`
     - `{agencyIcons['FSS']}` → `<AgencyIcon code="FSS" />`
   - `className="w-5 h-5"` 기본값이므로 대부분 prop 없이 호출 가능.

3. **동작 확인**:
   - `npm run build` + `npm run test` 로 빌드 + 테스트 통과.
   - 수동 확인 (개발자): 사이드바의 모든 agency 아이콘이 동일한 모양으로 렌더되는지 (AC 자동 검증 아님, 수동 체크).

## Acceptance Criteria

```bash
# 1) 신규 파일 존재
test -f web/components/dashboard/AgencyIcon.tsx

# 2) DashboardV2.tsx 에서 agencyIcons record 가 제거되었는가
! grep -q "agencyIcons: Record<string, React.ReactNode>" web/components/dashboard/DashboardV2.tsx
! grep -q "agencyIcons\[" web/components/dashboard/DashboardV2.tsx

# 3) AgencyIcon import 가 들어갔는가
grep -q "import AgencyIcon from './AgencyIcon'" web/components/dashboard/DashboardV2.tsx

# 4) 10개 case 가 모두 AgencyIcon 안에 있는가
python3 - <<'PY'
import re
with open('web/components/dashboard/AgencyIcon.tsx') as f:
    src = f.read()
codes = ['MOEF','FSC','FSS','BOK','FSC_REG','FSS_REG','FSS_REG_INFO','FSS_SANCTION','FSS_MGMT_NOTICE']
missing = [c for c in codes if f"case '{c}'" not in src and f'case "{c}"' not in src]
assert not missing, f"AgencyIcon missing cases: {missing}"
print("all 9 agency cases present")
PY

# 5) 빌드 + 테스트 통과
cd web && npm run build
cd web && npm run test

# 6) Sidebar closure 는 여전히 존재 (phase 4 의 몫)
grep -q "const Sidebar = () =>" web/components/dashboard/DashboardV2.tsx
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/9-round7-dashboard-decomposition/index.json`의 phase 2 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **SVG path / attribute 한 글자도 바꾸지 마라**. 원본 마크업을 그대로 옮겨라. 특히 `strokeLinecap="round"`, `strokeLinejoin="round"`, `strokeWidth={1.5}`, `viewBox="0 0 24 24"` 등.
- 9개 agency code 전체를 커버 (실제 쓰이는 건 9개 — 코드는 `pressAgencies(4) + regulationAgencies(3) + sanctionAgencies(2) = 9`. `FSC_REG` 는 FSC 와 같은 아이콘을 재사용하는 현재 구현을 따라 별도 case 로 둔다).
- Sidebar closure 는 **phase 4 의 몫**. phase 2 에서는 `agencyIcons[code]` 호출부만 치환하고, 클로저 자체는 그대로 둔다.
- `agencyIcons` 변수명을 다른 이름으로 rename 하지 마라. 삭제할 뿐.
- 기본 className 은 `w-5 h-5` 로 고정 (원본과 동일). 사이즈를 다르게 주고 싶은 호출처가 있으면 `className` prop 으로 override.
- `AgencyIcon.tsx` 는 `.tsx` (JSX 있음).
- React import 필요 (`import React from 'react'`) — Next.js + React 19 에서는 자동 JSX transform 이라 생략 가능하나, 명시적으로 두어도 무방.
