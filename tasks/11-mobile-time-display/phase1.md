# Phase 1: schema-contract

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 이해하라:

- `/home/pacer/projects/reg_brief/CLAUDE.md`
- `/home/pacer/projects/reg_brief/docs/ARCHITECTURE.md`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`
- `/home/pacer/projects/reg_brief/.cross-review/20260504T040604Z/round_1/author_v2.md`

그리고 아래 파일을 읽어 현재 스키마 스냅샷과 enum 패턴을 확인하라:

- `/home/pacer/projects/reg_brief/db/schema.sql`
- `/home/pacer/projects/reg_brief/scripts/v2_schema_setup.sql`
- `/home/pacer/projects/reg_brief/src/config/agency_codes.py`

이전 phase의 작업물은 없다. 이 phase가 task 11의 첫 phase다.

## 작업 내용

목표: `articles.published_at_source` 데이터 계약을 코드와 문서에 명확히 추가한다. 실제 live DB에는 접근하거나 DDL을 적용하지 않는다. 이 phase는 idempotent migration artifact와 로컬 스키마 문서 동기화까지만 수행한다.

1. `db/migrations/20260504_add_published_at_source.sql` 파일을 새로 만든다.
   - 디렉터리가 없으면 생성한다.
   - SQL은 idempotent 해야 한다.
   - `public.articles`에 nullable `published_at_source text` 컬럼을 추가한다.
   - 허용 값은 `null`, `'source'`, `'collected_fallback'`만 되도록 CHECK constraint를 둔다.
   - constraint 이름은 `articles_published_at_source_check`로 한다.
   - 컬럼 comment에 “source = 실제 발행시각, collected_fallback = 수집시각 fallback” 의미를 남긴다.

2. `db/schema.sql`을 동기화한다.
   - `articles` 테이블 정의에 `published_at_source TEXT`를 추가한다.
   - 같은 CHECK constraint를 추가한다.
   - 기존 stale warning 주석은 유지한다.

3. `scripts/v2_schema_setup.sql`을 동기화한다.
   - `published_at_source text null` 컬럼과 CHECK constraint를 추가한다.
   - 파일의 stale warning은 유지한다.

4. `docs/SCHEMA.md`를 동기화한다.
   - `published_at_source` 행을 `articles` 컬럼 표에 추가한다.
   - 허용 값과 null의 의미를 설명하는 짧은 섹션을 추가한다.
   - 기존 row는 `null`로 두며 추정 보정하지 않는다는 정책을 명시한다.

5. `src/config/agency_codes.py`에 Python enum을 추가한다.
   - 이름: `PublishedAtSource`
   - 값:
     - `SOURCE = "source"`
     - `COLLECTED_FALLBACK = "collected_fallback"`
   - `AgencyCode`, `ArticleCategory`와 동일하게 `str, Enum`을 상속하고 `__str__`에서 `self.value`를 반환한다.
   - 기존 enum 값과 주석은 불필요하게 바꾸지 않는다.

6. generated Supabase 타입 파일이 있는지 확인한다.
   - `rg --files | rg 'database\\.types|supabase.*types|types\\.database|schema\\.types'`
   - 현재 baseline에서는 명시적 generated type 파일이 보이지 않는다. 새로 발견되면 `published_at_source`를 반영한다. 없으면 새 타입 파일을 만들지 않는다.

## Acceptance Criteria

```bash
# 1) migration artifact 존재
test -f db/migrations/20260504_add_published_at_source.sql
grep -q "published_at_source" db/migrations/20260504_add_published_at_source.sql
grep -q "articles_published_at_source_check" db/migrations/20260504_add_published_at_source.sql
grep -q "IF NOT EXISTS" db/migrations/20260504_add_published_at_source.sql
grep -q "'source'" db/migrations/20260504_add_published_at_source.sql
grep -q "'collected_fallback'" db/migrations/20260504_add_published_at_source.sql
grep -q "COMMENT ON COLUMN public.articles.published_at_source" db/migrations/20260504_add_published_at_source.sql
! grep -Eiq '\bupdate\b|\bdelete\b' db/migrations/20260504_add_published_at_source.sql

# 2) schema snapshots 동기화
grep -q "published_at_source" db/schema.sql
grep -q "published_at_source" scripts/v2_schema_setup.sql
grep -q "published_at_source" docs/SCHEMA.md
grep -q "'source'" db/schema.sql
grep -q "'collected_fallback'" db/schema.sql

# 3) Python enum 존재
grep -q "class PublishedAtSource" src/config/agency_codes.py
grep -q 'SOURCE = "source"' src/config/agency_codes.py
grep -q 'COLLECTED_FALLBACK = "collected_fallback"' src/config/agency_codes.py

# 4) Python tests
venv/bin/python -m pytest tests/unit -q
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/11-mobile-time-display/index.json`의 phase 1 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황, 예를 들어 live Supabase에 직접 migration 적용을 요구받았지만 인증이 없는 경우에는 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- live DB에 DDL을 직접 적용하지 마라. 이 phase는 migration 파일과 문서 동기화만 한다.
- 기존 row의 `published_at_source` 값을 추정 보정하는 SQL을 작성하지 마라.
- migration 파일에 기존 row를 갱신하거나 삭제하는 `UPDATE`/`DELETE`를 넣지 마라.
- `published_at`의 의미나 기존 인덱스/정렬 정책을 바꾸지 마라.
- `source_updated`, `manual_backfill` 같은 추가 값을 만들지 마라. 이번 task의 허용 값은 두 개와 null뿐이다.
- `src/config/agency_codes.py`의 기존 enum 이름과 값은 바꾸지 마라.
