# Design: #3 농식품부(MAFRA) 추가

**Date**: 2026-04-10
**Status**: Approved
**Scope**: 기능추가 sub-project #3

## Summary

농식품부(MAFRA) 보도자료를 기존 수집 파이프라인에 추가한다. RSS 피드가
존재하므로 새 scraper 없이 기존 rss_parser + content_scraper를 재사용.
대시보드에서 바로 노출되도록 frontend 매핑도 함께 추가한다.

## 수집 방식

- **RSS**: `https://www.mafra.go.kr/bbs/home/792/rssList.do?row=50`
  - RSS 2.0, title + link + pubDate + author 제공. description 없음.
  - 절대 URL (`http://www.mafra.go.kr/bbs/home/792/{id}/artclView.do`)
- **본문 scrape**: 상세 페이지의 `.view_contents` selector
  - 게시글 2건(577570, 577573)에서 검증. 순수 본문만, 1003~2247자.
- **category**: `press_release`

## 변경 파일 (7개)

### Backend/Config (2개)

**`config/agencies.json`** — MAFRA 항목 추가:
```json
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

**`src/config/agency_codes.py`** — `MAFRA = "MAFRA"` 추가 (기존 `__str__`
override가 적용된 enum).

### Test (1개)

**`tests/unit/config/test_agency_loader.py`**:
- `assert len(agencies) == 9` → `== 10`
- `assert "MAFRA" in codes` 추가

### Frontend (4개)

**`web/components/dashboard/constants.ts`**:
- `pressAgencies`에 `'MAFRA'` 추가
- `agencyNames`에 `'MAFRA': '농식품부'` 추가

**`web/components/dashboard/NewsCard.tsx`**:
- `getAgencyColor`: `if (agency.includes('MAFRA')) return 'bg-emerald-100 text-emerald-700'`
- `getAgencyName`: map에 `'MAFRA': '농식품부'` 추가

**`web/components/dashboard/DateSection.tsx`**:
- `agencyConfig`에 `'MAFRA': { name: '농식품부', className: 'bg-emerald-100 text-emerald-700' }` 추가

**`web/components/dashboard/AgencyIcon.tsx`**:
- MAFRA case 추가 (나뭇잎 SVG 아이콘)

### 변경 불필요 (확인 완료)

- `DashboardV2.tsx` — `pressAgencies` import 사용, constants.ts 변경으로 자동 반영
- `Sidebar.tsx` — `pressAgencies`/`agencyOrder` import 기반, 동일
- `rss_parser.py` — agencies.json 동적 읽기
- `content_scraper.py` — selector.content를 agencies.json에서 읽기
- `pipeline.py` — agency_config 기반 동적 라우팅

## 색상

`bg-emerald-100 text-emerald-700` — 기존 FSC green과 구분되는 농림 계열.

## 하지 않는 것

- 새 scraper 파일 생성
- pipeline.py / rss_parser.py / content_scraper.py 수정
- DashboardV2.tsx / Sidebar.tsx 수정
- 기관별 탭 UI (sub-project #4 범위)

## Verification

1. `pytest tests/` 통과 (len == 10, "MAFRA" in codes)
2. `cd web && npm test` 통과
3. `cd web && npx tsc --noEmit` 통과
4. RSS fetch smoke: MAFRA RSS에서 항목 1개 이상 반환
5. Content scrape smoke: 반환 link 1개의 본문이 `.view_contents`로 50자 이상
6. Frontend 노출: `pressAgencies`에 `'MAFRA'` 포함, `agencyNames['MAFRA'] === '농식품부'`

## 분량

총 ~18줄 변경. 7개 파일.
