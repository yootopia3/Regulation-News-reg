# Sub-Project #4: AgencyChipBar — 기관별 필터 칩 바

- **날짜**: 2026-04-10
- **상태**: 설계 확정, 구현 대기
- **접근법**: A (독립 컴포넌트 + 기존 필터 상태 공유)

## 1. 목적

모바일(사이드바 없음)과 데스크탑 모두에서, 현재 카테고리의 기관 목록을
가로 스크롤 칩 바로 표시하여 기관 필터를 빠르게 토글할 수 있게 한다.
사이드바는 그대로 유지한다.

## 2. 컴포넌트

### AgencyChipBar

**파일**: `web/components/dashboard/AgencyChipBar.tsx` (신규)

**Props**:

```ts
interface AgencyChipBarProps {
  currentCategory: DashboardCategory
  selectedAgency: string | null
  onSelectAgency: (agency: string | null) => void
}
```

**토글 로직**:

```ts
const handleChipClick = (agency: string | null) => {
  if (agency === null || agency === selectedAgency) {
    onSelectAgency(null)  // "전체" 클릭 또는 같은 칩 재클릭 → 해제
  } else {
    onSelectAgency(agency)
  }
}
```

- `currentCategory`에 따라 `pressAgencies` / `regulationAgencies` /
  `sanctionAgencies` 중 해당 배열 선택
- 맨 앞에 "전체" 칩 (`agency = null`일 때 활성)

## 3. 칩 라벨 매핑

`constants.ts`에 `chipLabels` 추가:

```ts
export const chipLabels: Record<string, string> = {
  MOEF: '기재부',
  FSC: '금융위',
  FSS: '금감원',
  BOK: '한은',
  MAFRA: '농식품부',
  FSC_REG: '금융위',
  FSS_REG: '금감원(세칙)',
  FSS_REG_INFO: '금감원(제개정)',
  FSS_SANCTION: '제재',
  FSS_MGMT_NOTICE: '경영유의',
}
```

## 4. Sticky 계층 (고정 높이 기반)

| 요소 | 높이 | sticky top | z-index | 비고 |
|------|------|-----------|---------|------|
| Header | `h-[88px]` 고정 | `top-0` | `z-50` | 기존 유지 |
| View Toggle | ~52px | static | — | 스크롤 시 사라짐 |
| **AgencyChipBar** | **`h-[52px]` 고정** | **`top-[88px]`** | **`z-40`** | Header 바로 아래 |
| DateSection header | 가변 | **`top-[140px]`** | `z-30` | 88 + 52 = 140px |

**높이 고정 방법**:
- 컨테이너: `h-[52px]` 명시 고정
- 내부: `flex items-center` 수직 중앙 정렬
- 칩: `whitespace-nowrap` 줄바꿈 방지
- 오버플로우: `overflow-x-auto scrollbar-hide` 가로 스크롤

**DateSection 변경**: 기존 `top-28`(112px) → `top-[140px]`

**Sticky offset 산출**:
```
DateSection.top = Header.height(88px) + ChipBar.height(52px) = 140px
```

## 5. 배치 순서

```
┌─ Header ──────────────────────────────┐ sticky top-0 z-50
│  [☰]  [검색바]                  [⚙]  │ h-[88px]
├───────────────────────────────────────┤
│      [날짜별 ● | 리스트]              │ static
├───────────────────────────────────────┤
│ [전체] [금융위] [금감원] [기재부] ...  │ sticky top-[88px] z-40, h-[52px]
├───────────────────────────────────────┤
│  2026. 4. 10 (목)  총 12건            │ sticky top-[140px] z-30
│  [금융위 3] [금감원 5] [기재부 4]     │
├───────────────────────────────────────┤
│  NewsCard ...                         │
```

## 6. 스타일

**컨테이너**:
```
sticky top-[88px] z-40 h-[52px]
bg-white/95 backdrop-blur-sm border-b border-gray-100
flex items-center gap-2 px-4
overflow-x-auto scrollbar-hide
```

**칩**:
```
whitespace-nowrap rounded-full px-4 py-2 text-sm font-bold
transition-all duration-200 flex-shrink-0
```
- 활성: `bg-gray-900 text-white shadow-md`
- 비활성: `text-gray-500 hover:text-gray-900 bg-transparent`

## 7. 상태 동기화

- 칩 ↔ 사이드바: 동일한 `selectedAgency` 상태 공유, 양방향 자동 동기화
- 카테고리 변경: 기존 핸들러가 `selectedAgency = null`로 리셋 →
  칩 바 "전체" 활성, 칩 목록도 새 카테고리용으로 교체

## 8. 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `web/components/dashboard/AgencyChipBar.tsx` | **신규** — 칩 바 컴포넌트 (h-[52px] 고정, 토글 로직) |
| `web/components/dashboard/constants.ts` | `chipLabels` 맵 추가 |
| `web/components/dashboard/DashboardV2.tsx` | View Toggle 아래에 `<AgencyChipBar>` 배치 |
| `web/components/dashboard/DateSection.tsx` | `top-28` → `top-[140px]` |
| `web/__tests__/components/dashboard/AgencyChipBar.test.tsx` | **신규** — 8개 테스트 |

## 9. 테스트 케이스

파일: `web/__tests__/components/dashboard/AgencyChipBar.test.tsx`

| # | 테스트 | 검증 내용 |
|---|--------|-----------|
| 1 | 카테고리별 칩 목록 렌더링 | `press_release` → 전체+5개, `regulation_notice` → 전체+3개, `sanction_notice` → 전체+2개 |
| 2 | 칩 라벨이 한글 약칭 | "FSC"가 아닌 "금융위"로 표시 |
| 3 | 기관 칩 클릭 → 선택 | 금융위 클릭 시 `onSelectAgency('FSC')` 호출 |
| 4 | 같은 칩 재클릭 → 해제 | 이미 FSC 선택 상태에서 금융위 재클릭 → `onSelectAgency(null)` |
| 5 | "전체" 칩 클릭 → 해제 | `onSelectAgency(null)` 호출 |
| 6 | 카테고리 변경 시 칩 목록 교체 | `currentCategory` prop 변경 → 해당 카테고리 기관만 표시 |
| 7 | 활성 칩 스타일 적용 | `selectedAgency`에 해당하는 칩만 active 클래스 |
| 8 | "전체" 기본 활성 | `selectedAgency=null`일 때 "전체" 칩에 active 클래스 |

## 10. Verification

- `cd web && npm test` — 기존 + 신규 테스트 전체 pass
- `cd web && npx tsc --noEmit` — 타입 체크 pass
- 브라우저: 데스크탑/모바일 표시, sticky 동작, 칩 토글, 사이드바 동기화
