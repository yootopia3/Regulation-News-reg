# Phase 5: report-modal-type-fix

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 P1-4e, §7.2, §8.2 phase 5)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx` — phase 1–4 가 적용된 상태. 특히 본문 끝부분의 ReportModal 호출:
  ```tsx
  <ReportModal
      isOpen={isReportModalOpen}
      onClose={() => setIsReportModalOpen(false)}
      article={selectedArticle as any}
  />
  ```
  `selectedArticle: Article | null` 인데 `as any` 로 우회됨.
- `/home/pacer/projects/reg_brief/web/components/ReportModal.tsx` — 현재 `article` prop 의 타입 정의를 확인하라. (DashboardV2 와 미스매치인 부분이 무엇인지 식별 — 추가 필드, 다른 이름, 더 좁은 타입 등)
- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx` — `Article` 타입의 정확한 정의.

이전 phase의 작업물도 확인하라:

- phase 1–4 의 산출물.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: `DashboardV2.tsx` 의 `selectedArticle as any` 캐스트를 제거. ReportModal 의 `article` prop 타입과 `Article` 타입을 양방향으로 일치시킨다. **런타임 동작 변경 0**.

1. **현황 파악**: `web/components/ReportModal.tsx` 의 `article` prop 타입을 먼저 확인. 가능한 경우의 수:
   - (a) `article: any` → 그냥 `Article` 로 좁히기.
   - (b) `article: { id, title, content, agency, ...specific fields }` → DashboardV2 의 `Article` 과 필드가 다름. 양쪽을 호환 가능한 타입으로 좁힌다.
   - (c) `article: SomeOtherArticleType` → 그 타입의 정의가 어디 있는지 따라가서 `Article` 과의 차이를 식별.

2. **수정 전략 (위 경우에 따라 다름)**:

   **경우 (a)**: ReportModal 의 `article: any` 를 `article: Article` 로 변경. `import { Article } from './dashboard/NewsCard'`. 빌드 통과 확인.

   **경우 (b) 또는 (c)**: 두 가지 옵션 중 보수적으로 (b-1) 선택:
   - **(b-1)**: `Article` 타입에 ReportModal 이 요구하는 optional 필드를 추가. 예: `id?: number`, `analysis_result?: { keywords?: string[]; ... }`. 런타임 동작 변경 없음.
   - **(b-2)**: ReportModal 의 prop 타입을 ReportModal 측에서 좁힌 `ArticleForReport` 로 따로 정의 + DashboardV2 가 그 타입으로 캐스트 (단, `as any` 가 아닌 정확한 매핑).
   - 우선 (b-1) 시도. 그래도 마찰이 크면 (b-2) 로 이동. (b-2) 도 어려우면 phase 5 를 `error` 로 마킹하고 `error_message` 에 마찰 지점을 기록.

3. **`as any` 제거**:
   - `DashboardV2.tsx` 에서 `article={selectedArticle as any}` → `article={selectedArticle}`.
   - `selectedArticle` 의 타입이 `Article | null` 이므로 ReportModal 의 prop 도 `Article | null` 또는 `Article` 이어야 한다. 후자라면 `selectedArticle &&` guard 가 이미 있는 (`{isReportModalOpen && selectedArticle && (...)`) 조건 안에서 `selectedArticle!` 또는 narrowing 으로 처리.

4. **회귀 체크**: ReportModal 의 내부 동작 (Gemini 호출, markdown 렌더 등) 은 절대 건드리지 마라. 타입만.

5. **빌드/테스트**: `npm run build` (tsc 컴파일) 가 통과해야 한다. 기존 vitest 테스트 (`web/__tests__/api/report.test.ts`) 도 통과.

## Acceptance Criteria

```bash
# 1) `as any` 캐스트가 사라졌는가
! grep -q "as any" web/components/dashboard/DashboardV2.tsx

# 2) 빌드 통과 (tsc strict 검사)
cd web && npm run build

# 3) 테스트 통과
cd web && npm run test

# 4) ReportModal 의 article prop 타입이 명시되어 있는가 (any 가 아닌가)
python3 - <<'PY'
import re
with open('web/components/ReportModal.tsx') as f:
    src = f.read()
# article prop 타입 라인이 'article: any' 가 아닌지 확인
m = re.search(r'article\s*:\s*(\w+)', src)
if m:
    assert m.group(1) != 'any', "ReportModal article prop should not be `any`"
    print(f"ReportModal article prop type: {m.group(1)}")
else:
    print("ReportModal article prop type not found via simple regex (manual check needed)")
PY
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/9-round7-dashboard-decomposition/index.json`의 phase 5 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
ReportModal 의 prop 타입이 너무 복잡해서 narrowing 이 의미 없는 값이 되어 버린다면 `error` 로 마킹하고 `error_message` 에 어떤 필드가 충돌했는지 명시.

## 주의사항

- **런타임 동작 변경 금지**. 타입만 좁힌다. 새 prop 추가, 새 props validation, 새 effect 일체 금지.
- ReportModal 의 비즈니스 로직 (Gemini 호출, supabase update, markdown rendering) 절대 건드리지 마라.
- `Article` 타입에 새 필드를 추가할 때는 **optional (`?`)** 로 추가. required 로 만들면 다른 곳에서 컴파일 에러.
- `selectedArticle as any` → `selectedArticle as Article` 같은 cast-only 변경은 지양 (`as any` 를 `as Article` 로 바꾸는 것은 typesafe 가 아니라 우회). 정상 narrowing 이 가능한 형태로 가야 한다.
- `selectedArticle!` non-null assertion 은 `&& selectedArticle &&` guard 가 있는 conditional 안에서만 허용.
- 다른 컴포넌트 (`NewsCard.tsx`, `DateSection.tsx`, `Header.tsx`) 의 prop 타입은 건드리지 마라.
- TypeScript strict 옵션이 켜져 있으므로 `npm run build` 가 진짜 검증의 척도다.
