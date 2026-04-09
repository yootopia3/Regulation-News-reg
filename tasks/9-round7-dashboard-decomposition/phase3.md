# Phase 3: new-badge-hook

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C3 / P1-4d, §7.2, §8.2 phase 3)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/web/components/dashboard/DashboardV2.tsx` — phase 1·2 가 적용된 상태. 특히:
  - L7 상단 import: `import { getLastVisitTime, updateLastVisitTime, isArticleNew, countNewArticles } from '@/utils/newArticleTracker'` — `countNewArticles` 는 **사용처 없음** (죽은 import).
  - L37–56 의 3개 `useMemo` 블록: `hasNewPress`, `hasNewReg`, `hasNewSanction`. 동일한 패턴 (category 비교 + `isArticleNew` 체크) 이 3회 반복.
- `/home/pacer/projects/reg_brief/web/utils/newArticleTracker.ts` — `isArticleNew`, `countNewArticles` 정의. 시그니처와 카테고리 키 컨벤션 확인.
- `/home/pacer/projects/reg_brief/web/components/dashboard/NewsCard.tsx` — `Article` 타입 정의 (category, created_at, published_at 필드 확인).

이전 phase의 작업물도 확인하라:

- `web/components/dashboard/constants.ts` (phase 1)
- `web/components/dashboard/AgencyIcon.tsx` (phase 2)
- 각각이 적용된 `DashboardV2.tsx`

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: 3개 `useMemo` 의 NEW 뱃지 계산 로직을 **단일 훅** 으로 추출하고, 동시에 죽은 `countNewArticles` import 를 제거.

1. **신규 파일**: `web/components/dashboard/useHasNewByCategory.ts`
   - 시그니처:
     ```typescript
     import { useMemo } from 'react'
     import { isArticleNew } from '@/utils/newArticleTracker'
     import { Article } from './NewsCard'

     export type HasNewByCategory = {
         hasNewPress: boolean
         hasNewReg: boolean
         hasNewSanction: boolean
     }

     export function useHasNewByCategory(
         articles: Article[],
         lastVisitTime: Date | null,
     ): HasNewByCategory {
         return useMemo(() => {
             const hasNewPress = articles.some(a =>
                 (a.category === 'press_release' || !a.category) &&
                 isArticleNew(a.created_at || a.published_at, lastVisitTime)
             )
             const hasNewReg = articles.some(a =>
                 a.category === 'regulation_notice' &&
                 isArticleNew(a.created_at || a.published_at, lastVisitTime)
             )
             const hasNewSanction = articles.some(a =>
                 a.category === 'sanction_notice' &&
                 isArticleNew(a.created_at || a.published_at, lastVisitTime)
             )
             return { hasNewPress, hasNewReg, hasNewSanction }
         }, [articles, lastVisitTime])
     }
     ```
   - **로직 동일성 보존**: 카테고리 매칭 (`'press_release' || !a.category`), `created_at || published_at` fallback 모두 원본과 1:1 일치.

2. **`DashboardV2.tsx` 수정**:
   - 상단 import 를 다음과 같이 수정:
     - **삭제**: `countNewArticles` (죽은 import — 본문에서 사용처 0).
     - **추가**: `import { useHasNewByCategory } from './useHasNewByCategory'`
     - 결과 (예시):
       ```typescript
       import { getLastVisitTime, updateLastVisitTime, isArticleNew } from '@/utils/newArticleTracker'
       ...
       import { useHasNewByCategory } from './useHasNewByCategory'
       ```
   - L37–56 의 3개 `useMemo` 블록 **삭제**.
   - 본문에서 `lastVisitTime` 이 정의된 직후 (state 선언부 끝나는 지점) 한 줄 추가:
     ```typescript
     const { hasNewPress, hasNewReg, hasNewSanction } = useHasNewByCategory(articles, lastVisitTime)
     ```
   - **`isArticleNew` 자체는 다른 곳에서도 쓰이므로 import 에 남겨둔다** (예: `processedData` 의 `articlesWithNewFlag` 매핑에서 `isArticleNew(article.created_at || article.published_at, lastVisitTime)` 호출).

3. **회귀 확인**:
   - Sidebar closure 안의 `{hasNewPress && (...)}`, `{hasNewReg && (...)}`, `{hasNewSanction && (...)}` 사용처는 그대로 둔다 — 변수명 동일.
   - `processedData` 의 `articlesWithNewFlag` 매핑에서 사용하는 `isArticleNew` 도 그대로 동작.

## Acceptance Criteria

```bash
# 1) 신규 파일 존재
test -f web/components/dashboard/useHasNewByCategory.ts

# 2) 죽은 import 제거
! grep -q "countNewArticles" web/components/dashboard/DashboardV2.tsx

# 3) 인라인 useMemo 3 개가 사라졌는가
! grep -q "const hasNewPress = useMemo" web/components/dashboard/DashboardV2.tsx
! grep -q "const hasNewReg = useMemo" web/components/dashboard/DashboardV2.tsx
! grep -q "const hasNewSanction = useMemo" web/components/dashboard/DashboardV2.tsx

# 4) 새 훅 호출이 들어갔는가
grep -q "useHasNewByCategory(articles, lastVisitTime)" web/components/dashboard/DashboardV2.tsx

# 5) isArticleNew 는 여전히 import 되어 있는가 (다른 곳에서 사용 중)
grep -q "isArticleNew" web/components/dashboard/DashboardV2.tsx

# 6) 빌드 + 테스트 통과
cd web && npm run build
cd web && npm run test
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/9-round7-dashboard-decomposition/index.json`의 phase 3 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **로직 동일성**: `isArticleNew(a.created_at || a.published_at, ...)` — fallback 순서 (`created_at` 먼저, `published_at` 다음) 를 절대 바꾸지 마라. 원본 의미는 "DB 에 created_at 이 있으면 그 시각, 없으면 published_at 시각" 이다.
- `'press_release' || !a.category` — `!a.category` 분기를 빠뜨리지 마라. 카테고리 미설정 article 을 press_release 로 흡수하는 것은 의도된 동작이다 (Round 4 전까지의 레거시 데이터 호환).
- `useMemo` 의존성 배열은 `[articles, lastVisitTime]` 만. 다른 변수 추가 금지.
- Hook 파일은 `.ts` (JSX 없음). React import 불필요 (`useMemo` 만 import).
- `countNewArticles` 가 죽은 import 임을 확신할 것: `grep -n "countNewArticles" web/components/dashboard/DashboardV2.tsx` 가 import 라인 1건만 잡혀야 한다 (사용처 0).
- Sidebar closure 안의 `hasNewPress / hasNewReg / hasNewSanction` 참조는 변수명이 동일하므로 자동으로 동작한다. 별도 prop drilling 없음 (sidebar 분리는 phase 4).
