# MAFRA Agency Addition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 농식품부(MAFRA) press releases to the collection pipeline and dashboard.

**Architecture:** RSS collection via existing `rss_parser.py`, content scrape via existing `content_scraper.py` with `.view_contents` selector, frontend exposure via `constants.ts` + component mappings. No new modules.

**Tech Stack:** Python (backend config/enum), TypeScript/React (dashboard components), pytest + vitest (tests)

**Spec:** `docs/superpowers/specs/2026-04-10-mafra-agency-design.md`

---

## Task 1: Backend — Test-first agency count update

**Files:**
- Modify: `tests/unit/config/test_agency_loader.py:39-44`

- [ ] **Step 1: Update test expectations for MAFRA**

```python
def test_load_agencies_returns_full_list():
    agencies = load_agencies()
    assert len(agencies) == 10
    codes = {a["code"] for a in agencies}
    assert "FSS_SANCTION" in codes
    assert "FSS_MGMT_NOTICE" in codes
    assert "MAFRA" in codes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/pacer/projects/reg_brief && python -m pytest tests/unit/config/test_agency_loader.py::test_load_agencies_returns_full_list -v`

Expected: FAIL — `assert 9 == 10`

---

## Task 2: Backend — Add MAFRA to config and enum

**Files:**
- Modify: `config/agencies.json:141` (before closing `]`)
- Modify: `src/config/agency_codes.py:29` (after FSS_MGMT_NOTICE)

- [ ] **Step 1: Add MAFRA entry to agencies.json**

Insert before the closing `]` on line 142:

```json
    ,
    {
      "code": "MAFRA",
      "name": "농식품부 (MAFRA)",
      "category": "press_release",
      "collection_method": "rss",
      "url": "https://www.mafra.go.kr/bbs/home/792/rssList.do?row=50",
      "base_url": "https://www.mafra.go.kr",
      "selector": {
        "content": ".view_contents"
      }
    }
```

- [ ] **Step 2: Add MAFRA to AgencyCode enum**

In `src/config/agency_codes.py`, after line 29 (`FSS_MGMT_NOTICE = "FSS_MGMT_NOTICE"`):

```python
    MAFRA = "MAFRA"
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd /home/pacer/projects/reg_brief && python -m pytest tests/unit/config/test_agency_loader.py -v`

Expected: ALL PASS (4 tests)

- [ ] **Step 4: Run full backend test suite**

Run: `cd /home/pacer/projects/reg_brief && python -m pytest tests/ -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add config/agencies.json src/config/agency_codes.py tests/unit/config/test_agency_loader.py
git commit -m "feat(mafra): add MAFRA agency to config, enum, and loader test"
```

---

## Task 3: Frontend — Dashboard mappings

**Files:**
- Modify: `web/components/dashboard/constants.ts:2,13`
- Modify: `web/components/dashboard/NewsCard.tsx:45,58`
- Modify: `web/components/dashboard/DateSection.tsx:26`
- Modify: `web/components/dashboard/AgencyIcon.tsx:17`

- [ ] **Step 1: Add MAFRA to constants.ts**

Line 2 — add `'MAFRA'` to `pressAgencies`:
```typescript
export const pressAgencies = ['MOEF', 'FSC', 'FSS', 'BOK', 'MAFRA'] as const
```

Line 13 — add to `agencyNames`:
```typescript
export const agencyNames: Record<string, string> = {
  'MOEF': '기획재정부',
  'FSC': '금융위원회',
  'FSS': '금융감독원',
  'BOK': '한국은행',
  'MAFRA': '농식품부',
}
```

- [ ] **Step 2: Add MAFRA to NewsCard.tsx color and name mappings**

In `getAgencyColor` (after line 45, the BOK check, before the gray fallback):
```typescript
        if (agency.includes('MAFRA')) return 'bg-emerald-100 text-emerald-700'
```

In `getAgencyName` map (line 58-63, add MAFRA):
```typescript
        const map: Record<string, string> = {
            'FSC': '금융위',
            'FSS': '금감원',
            'MOEF': '기재부',
            'BOK': '한은',
            'MAFRA': '농식품부'
        }
```

- [ ] **Step 3: Add MAFRA to DateSection.tsx agencyConfig**

In `agencyConfig` (line 26-36), add after the MOEF entry:
```typescript
        'MAFRA': { name: '농식품부', className: 'bg-emerald-100 text-emerald-700' },
```

- [ ] **Step 4: Add MAFRA case to AgencyIcon.tsx**

After the BOK case (line 17), before the FSC_REG case:
```tsx
        case 'MAFRA':
            return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>)
```

- [ ] **Step 5: Run TypeScript build check**

Run: `cd /home/pacer/projects/reg_brief/web && npx tsc --noEmit`

Expected: no errors

- [ ] **Step 6: Run frontend tests**

Run: `cd /home/pacer/projects/reg_brief/web && npm test`

Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add web/components/dashboard/constants.ts web/components/dashboard/NewsCard.tsx web/components/dashboard/DateSection.tsx web/components/dashboard/AgencyIcon.tsx
git commit -m "feat(mafra): add MAFRA to dashboard constants, card, date section, and icon"
```

---

## Task 4: Smoke verification

- [ ] **Step 1: RSS fetch smoke test**

Run:
```bash
cd /home/pacer/projects/reg_brief && source venv/bin/activate && python3 -c "
from src.collectors.rss_parser import fetch_rss_feed
items = fetch_rss_feed({
    'code': 'MAFRA',
    'name': '농식품부 (MAFRA)',
    'collection_method': 'rss',
    'url': 'https://www.mafra.go.kr/bbs/home/792/rssList.do?row=50',
    'base_url': 'https://www.mafra.go.kr'
})
print(f'Items: {len(items)}')
if items:
    print(f'First: {items[0][\"title\"][:60]}')
    print(f'Link: {items[0][\"link\"]}')
"
```

Expected: `Items:` > 0, title과 link가 정상 출력.

- [ ] **Step 2: Content scrape smoke test**

위 Step 1에서 나온 첫 번째 link를 사용:
```bash
cd /home/pacer/projects/reg_brief && source venv/bin/activate && python3 -c "
from src.collectors.content_scraper import fetch_content
url = '<Step 1에서 나온 link>'
config = {'code': 'MAFRA', 'selector': {'content': '.view_contents'}}
content = fetch_content(url, config)
print(f'Content length: {len(content) if content else 0}')
if content:
    print(f'Preview: {content[:100]}...')
"
```

Expected: `Content length:` >= 50, 한국어 본문 텍스트.

- [ ] **Step 3: Frontend constants verification**

Run:
```bash
cd /home/pacer/projects/reg_brief && grep -n "MAFRA" web/components/dashboard/constants.ts web/components/dashboard/NewsCard.tsx web/components/dashboard/DateSection.tsx web/components/dashboard/AgencyIcon.tsx
```

Expected: 각 파일에서 MAFRA 관련 줄이 1개 이상.

---

## Task 5 (Optional): Frontend test — MAFRA in pressAgencies

사용자 요청: "web/__tests__/components/dashboard/DashboardV2.test.tsx에 pressAgencies 반영이나 MAFRA 노출 경로를 한 번 더 잡아두면 좋다." 필수는 아님.

**Files:**
- Modify: `web/__tests__/components/dashboard/DashboardV2.test.tsx`

- [ ] **Step 1: Add pressAgencies import test**

기존 테스트 파일 끝에 추가:
```typescript
describe('MAFRA integration', () => {
    it('pressAgencies includes MAFRA', async () => {
        const { pressAgencies } = await import('@/components/dashboard/constants')
        expect(pressAgencies).toContain('MAFRA')
    })

    it('agencyNames maps MAFRA to 농식품부', async () => {
        const { agencyNames } = await import('@/components/dashboard/constants')
        expect(agencyNames['MAFRA']).toBe('농식품부')
    })
})
```

- [ ] **Step 2: Run test**

Run: `cd /home/pacer/projects/reg_brief/web && npm test`

Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add web/__tests__/components/dashboard/DashboardV2.test.tsx
git commit -m "test(mafra): verify MAFRA in pressAgencies and agencyNames"
```
