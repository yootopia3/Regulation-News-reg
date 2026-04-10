# AgencyChipBar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sticky horizontal chip bar below the view toggle so users can filter articles by agency without the sidebar.

**Architecture:** New `AgencyChipBar` component reads `currentCategory` to show the right agency list, shares `selectedAgency` state with the existing sidebar via props from `DashboardV2`. Chip click toggles the filter. Fixed height `h-[52px]` ensures stable sticky stacking with Header (88px) and DateSection (140px).

**Tech Stack:** TypeScript, React, Tailwind CSS, vitest + @testing-library/react

**Spec:** `docs/superpowers/specs/2026-04-10-agency-chip-bar-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `web/components/dashboard/constants.ts` | Modify | Add `chipLabels` map |
| `web/components/dashboard/AgencyChipBar.tsx` | Create | Chip bar component with toggle logic |
| `web/components/dashboard/DashboardV2.tsx` | Modify | Import and place `<AgencyChipBar>` below view toggle |
| `web/components/dashboard/DateSection.tsx` | Modify | Update sticky `top-28` → `top-[140px]` |
| `web/__tests__/components/dashboard/AgencyChipBar.test.tsx` | Create | 8 test cases for rendering, toggle, category switching |

---

## Task 1: Add `chipLabels` to constants

**Files:**
- Modify: `web/components/dashboard/constants.ts:31` (before `DashboardCategory` type)

- [ ] **Step 1: Write the failing test**

Create `web/__tests__/components/dashboard/AgencyChipBar.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'

describe('chipLabels', () => {
    it('maps all press agencies to Korean short names', async () => {
        const { chipLabels, pressAgencies } = await import('@/components/dashboard/constants')
        for (const code of pressAgencies) {
            expect(chipLabels[code]).toBeDefined()
        }
        expect(chipLabels['MOEF']).toBe('기재부')
        expect(chipLabels['FSC']).toBe('금융위')
        expect(chipLabels['FSS']).toBe('금감원')
        expect(chipLabels['BOK']).toBe('한은')
        expect(chipLabels['MAFRA']).toBe('농식품부')
    })

    it('maps all regulation agencies to Korean short names', async () => {
        const { chipLabels, regulationAgencies } = await import('@/components/dashboard/constants')
        for (const code of regulationAgencies) {
            expect(chipLabels[code]).toBeDefined()
        }
        expect(chipLabels['FSC_REG']).toBe('금융위')
        expect(chipLabels['FSS_REG']).toBe('금감원(세칙)')
        expect(chipLabels['FSS_REG_INFO']).toBe('금감원(제개정)')
    })

    it('maps all sanction agencies to Korean short names', async () => {
        const { chipLabels, sanctionAgencies } = await import('@/components/dashboard/constants')
        for (const code of sanctionAgencies) {
            expect(chipLabels[code]).toBeDefined()
        }
        expect(chipLabels['FSS_SANCTION']).toBe('제재')
        expect(chipLabels['FSS_MGMT_NOTICE']).toBe('경영유의')
    })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/pacer/projects/reg_brief/web && npx vitest run __tests__/components/dashboard/AgencyChipBar.test.tsx`

Expected: FAIL — `chipLabels is not defined` or `undefined`

- [ ] **Step 3: Add `chipLabels` to constants.ts**

In `web/components/dashboard/constants.ts`, add before the `DashboardCategory` type (line 31):

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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/pacer/projects/reg_brief/web && npx vitest run __tests__/components/dashboard/AgencyChipBar.test.tsx`

Expected: 3 tests PASS

- [ ] **Step 5: Type check**

Run: `cd /home/pacer/projects/reg_brief/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /home/pacer/projects/reg_brief
git add web/components/dashboard/constants.ts web/__tests__/components/dashboard/AgencyChipBar.test.tsx
git commit -m "feat(dashboard): add chipLabels map for agency short names"
```

---

## Task 2: Create AgencyChipBar component — rendering tests

**Files:**
- Create: `web/components/dashboard/AgencyChipBar.tsx`
- Modify: `web/__tests__/components/dashboard/AgencyChipBar.test.tsx`

- [ ] **Step 1: Add rendering tests to the test file**

Append to `web/__tests__/components/dashboard/AgencyChipBar.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'

describe('AgencyChipBar rendering', () => {
    it('renders "전체" + 5 press agency chips for press_release category', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency={null}
                onSelectAgency={() => {}}
            />
        )
        expect(screen.getByText('전체')).toBeInTheDocument()
        expect(screen.getByText('금융위')).toBeInTheDocument()
        expect(screen.getByText('금감원')).toBeInTheDocument()
        expect(screen.getByText('기재부')).toBeInTheDocument()
        expect(screen.getByText('한은')).toBeInTheDocument()
        expect(screen.getByText('농식품부')).toBeInTheDocument()
        expect(screen.getAllByRole('button')).toHaveLength(6) // 전체 + 5
    })

    it('renders "전체" + 3 regulation chips for regulation_notice category', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="regulation_notice"
                selectedAgency={null}
                onSelectAgency={() => {}}
            />
        )
        expect(screen.getByText('전체')).toBeInTheDocument()
        expect(screen.getAllByRole('button')).toHaveLength(4) // 전체 + 3
    })

    it('renders "전체" + 2 sanction chips for sanction_notice category', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="sanction_notice"
                selectedAgency={null}
                onSelectAgency={() => {}}
            />
        )
        expect(screen.getByText('전체')).toBeInTheDocument()
        expect(screen.getAllByRole('button')).toHaveLength(3) // 전체 + 2
    })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/pacer/projects/reg_brief/web && npx vitest run __tests__/components/dashboard/AgencyChipBar.test.tsx`

Expected: FAIL — `Cannot find module '@/components/dashboard/AgencyChipBar'`

- [ ] **Step 3: Create AgencyChipBar component**

Create `web/components/dashboard/AgencyChipBar.tsx`:

```tsx
import {
    pressAgencies,
    regulationAgencies,
    sanctionAgencies,
    chipLabels,
    DashboardCategory,
} from './constants'

interface AgencyChipBarProps {
    currentCategory: DashboardCategory
    selectedAgency: string | null
    onSelectAgency: (agency: string | null) => void
}

const agenciesByCategory: Record<DashboardCategory, readonly string[]> = {
    press_release: pressAgencies,
    regulation_notice: regulationAgencies,
    sanction_notice: sanctionAgencies,
}

export default function AgencyChipBar({ currentCategory, selectedAgency, onSelectAgency }: AgencyChipBarProps) {
    const agencies = agenciesByCategory[currentCategory]

    const handleChipClick = (agency: string | null) => {
        if (agency === null || agency === selectedAgency) {
            onSelectAgency(null)
        } else {
            onSelectAgency(agency)
        }
    }

    const activeClass = 'bg-gray-900 text-white shadow-md'
    const inactiveClass = 'text-gray-500 hover:text-gray-900 bg-transparent'

    return (
        <div className="sticky top-[88px] z-40 h-[52px] bg-white/95 backdrop-blur-sm border-b border-gray-100 flex items-center gap-2 px-4 overflow-x-auto scrollbar-hide">
            <button
                onClick={() => handleChipClick(null)}
                className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-bold transition-all duration-200 flex-shrink-0 ${selectedAgency === null ? activeClass : inactiveClass}`}
            >
                전체
            </button>
            {agencies.map(code => (
                <button
                    key={code}
                    onClick={() => handleChipClick(code)}
                    className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-bold transition-all duration-200 flex-shrink-0 ${selectedAgency === code ? activeClass : inactiveClass}`}
                >
                    {chipLabels[code] ?? code}
                </button>
            ))}
        </div>
    )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/pacer/projects/reg_brief/web && npx vitest run __tests__/components/dashboard/AgencyChipBar.test.tsx`

Expected: 6 tests PASS (3 chipLabels + 3 rendering)

- [ ] **Step 5: Type check**

Run: `cd /home/pacer/projects/reg_brief/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /home/pacer/projects/reg_brief
git add web/components/dashboard/AgencyChipBar.tsx web/__tests__/components/dashboard/AgencyChipBar.test.tsx
git commit -m "feat(dashboard): create AgencyChipBar component with category-based rendering"
```

---

## Task 3: Toggle and active-state tests

**Files:**
- Modify: `web/__tests__/components/dashboard/AgencyChipBar.test.tsx`

- [ ] **Step 1: Add toggle and active-state tests**

Append to `web/__tests__/components/dashboard/AgencyChipBar.test.tsx`:

```tsx
import { vi } from 'vitest'
import userEvent from '@testing-library/user-event'

describe('AgencyChipBar toggle logic', () => {
    it('calls onSelectAgency with agency code when a chip is clicked', async () => {
        const onSelectAgency = vi.fn()
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency={null}
                onSelectAgency={onSelectAgency}
            />
        )
        await userEvent.click(screen.getByText('금융위'))
        expect(onSelectAgency).toHaveBeenCalledWith('FSC')
    })

    it('calls onSelectAgency(null) when the same chip is clicked again (toggle off)', async () => {
        const onSelectAgency = vi.fn()
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency="FSC"
                onSelectAgency={onSelectAgency}
            />
        )
        await userEvent.click(screen.getByText('금융위'))
        expect(onSelectAgency).toHaveBeenCalledWith(null)
    })

    it('calls onSelectAgency(null) when "전체" chip is clicked', async () => {
        const onSelectAgency = vi.fn()
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency="FSC"
                onSelectAgency={onSelectAgency}
            />
        )
        await userEvent.click(screen.getByText('전체'))
        expect(onSelectAgency).toHaveBeenCalledWith(null)
    })
})

describe('AgencyChipBar active state', () => {
    it('applies active class to the selected agency chip', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency="FSC"
                onSelectAgency={() => {}}
            />
        )
        const fscButton = screen.getByText('금융위')
        expect(fscButton.className).toContain('bg-gray-900')
        const allButton = screen.getByText('전체')
        expect(allButton.className).not.toContain('bg-gray-900')
    })

    it('applies active class to "전체" when selectedAgency is null', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency={null}
                onSelectAgency={() => {}}
            />
        )
        const allButton = screen.getByText('전체')
        expect(allButton.className).toContain('bg-gray-900')
    })
})
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /home/pacer/projects/reg_brief/web && npx vitest run __tests__/components/dashboard/AgencyChipBar.test.tsx`

Expected: 11 tests PASS (3 chipLabels + 3 rendering + 3 toggle + 2 active state)

- [ ] **Step 3: Commit**

```bash
cd /home/pacer/projects/reg_brief
git add web/__tests__/components/dashboard/AgencyChipBar.test.tsx
git commit -m "test(dashboard): add toggle and active-state tests for AgencyChipBar"
```

---

## Task 4: Integrate into DashboardV2

**Files:**
- Modify: `web/components/dashboard/DashboardV2.tsx:14,227` (import + JSX placement)

- [ ] **Step 1: Add import**

In `web/components/dashboard/DashboardV2.tsx`, add after the Sidebar import (line 13):

```tsx
import AgencyChipBar from './AgencyChipBar'
```

- [ ] **Step 2: Place AgencyChipBar below View Toggle**

In `web/components/dashboard/DashboardV2.tsx`, find the View Toggle closing `</div>` (line 227). Insert immediately after it:

```tsx
                    {/* Agency Chip Bar (sticky filter) */}
                    <AgencyChipBar
                        currentCategory={currentCategory}
                        selectedAgency={selectedAgency}
                        onSelectAgency={setSelectedAgency}
                    />
```

The result in context — the View Toggle block ends, then the chip bar appears before the loading/content section:

```tsx
                    </div>  {/* end View Toggle */}

                    {/* Agency Chip Bar (sticky filter) */}
                    <AgencyChipBar
                        currentCategory={currentCategory}
                        selectedAgency={selectedAgency}
                        onSelectAgency={setSelectedAgency}
                    />

                    {loading ? (
```

- [ ] **Step 3: Type check**

Run: `cd /home/pacer/projects/reg_brief/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 4: Run all tests**

Run: `cd /home/pacer/projects/reg_brief/web && npx vitest run`

Expected: All tests PASS (existing DashboardV2 tests + new AgencyChipBar tests)

- [ ] **Step 5: Commit**

```bash
cd /home/pacer/projects/reg_brief
git add web/components/dashboard/DashboardV2.tsx
git commit -m "feat(dashboard): integrate AgencyChipBar below view toggle"
```

---

## Task 5: Update DateSection sticky offset

**Files:**
- Modify: `web/components/dashboard/DateSection.tsx:44`

- [ ] **Step 1: Update sticky top value**

In `web/components/dashboard/DateSection.tsx`, line 44, change:

```tsx
                className="sticky top-28 z-30 mb-3 cursor-pointer select-none group"
```

to:

```tsx
                className="sticky top-[140px] z-30 mb-3 cursor-pointer select-none group"
```

Rationale: Header (88px) + AgencyChipBar (52px) = 140px.

- [ ] **Step 2: Type check**

Run: `cd /home/pacer/projects/reg_brief/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Run all tests**

Run: `cd /home/pacer/projects/reg_brief/web && npx vitest run`

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd /home/pacer/projects/reg_brief
git add web/components/dashboard/DateSection.tsx
git commit -m "fix(dashboard): adjust DateSection sticky top for AgencyChipBar (88+52=140px)"
```

---

## Task 6: Final verification

- [ ] **Step 1: Full test suite**

Run: `cd /home/pacer/projects/reg_brief/web && npx vitest run`

Expected: All tests PASS

- [ ] **Step 2: TypeScript type check**

Run: `cd /home/pacer/projects/reg_brief/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Visual verification checklist**

Start dev server: `cd /home/pacer/projects/reg_brief/web && npm run dev`

Check in browser:

- [ ] Desktop: chip bar visible below view toggle, above date sections
- [ ] Desktop: chip bar stays sticky when scrolling (below header)
- [ ] Desktop: DateSection headers stick below chip bar, no overlap
- [ ] Desktop: clicking a chip filters articles to that agency
- [ ] Desktop: clicking the same chip again deselects (shows all)
- [ ] Desktop: clicking "전체" shows all articles
- [ ] Desktop: sidebar agency selection syncs with chip bar active state
- [ ] Desktop: switching category changes chip list (보도자료 → 규제개정)
- [ ] Mobile: chip bar visible (no sidebar)
- [ ] Mobile: horizontal scroll if chips overflow
- [ ] Mobile: chip toggle works same as desktop
