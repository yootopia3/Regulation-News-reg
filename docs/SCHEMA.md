# Database Schema (As-Built)

**Database**: PostgreSQL (Supabase)
**Table**: `public.articles`
**Reference SQL**: `db/schema.sql`

## 1. Table Structure

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | No | `gen_random_uuid()` | Primary key |
| `created_at` | `timestamptz` | No | `now()` | Row creation time. Also used as fallback display time for legacy/date-only rows. |
| `title` | `text` | No | - | Article title |
| `link` | `text` | No | - | Unique source link for deduplication |
| `agency` | `text` | No | - | Agency code from `config/agencies.json` |
| `content` | `text` | Yes | - | Original body text for backend/report generation |
| `published_at` | `timestamptz` | No | - | Publication timestamp or collection fallback timestamp |
| `published_at_source` | `text` | Yes | - | `source`, `collected_fallback`, or `null` |
| `analysis_result` | `jsonb` | Yes | - | AI analysis/cache payload |
| `embedding` | `vector(1536)` | Yes | - | Legacy nullable placeholder. Current code does not write embeddings. |
| `view_count` | `integer` | No | `0` | Reserved v2 field. Current client does not update it. |
| `star_rating` | `integer` | Yes | - | Optional manual 1-5 rating used before AI score fallback |
| `is_trending` | `boolean` | No | `false` | Reserved v2 field |
| `category` | `varchar(50)` | Yes | `press_release` | Dashboard category: `press_release`, `regulation_notice`, or `sanction_notice` |
| `source_org` | `text` | Yes | - | Source organization code for RSS-first collectors such as `KFB` |
| `source_name` | `text` | Yes | - | Human-readable source organization name such as `은행연합회` |
| `subcategory` | `text` | Yes | - | Collector-specific subtype such as `bank_association_press` |
| `dedup_key` | `text` | Yes | - | Stable collector key used for upsert when available |

## 2. Constraints And Indexes

- Primary key: `articles_pkey` on `id`
- Unique key: `articles_link_key` on `link`
- Unique key: `articles_dedup_key_key` on `dedup_key` for collectors that provide stable source keys
- Check: `articles_agency_check` allows the current agency codes in `config/agencies.json`, including `KFB`
- Check: `articles_published_at_source_check` allows only `source`, `collected_fallback`, or `null`
- Check: `star_rating` must be between 1 and 5 when present
- Indexes: `articles_agency_idx`, `articles_published_at_idx`, `idx_articles_category`

Agency codes are application-configured in `config/agencies.json`; when a new agency is added, `articles_agency_check` must be updated before collector writes are enabled.

## 3. RLS And Privileges

`public.articles` has Row Level Security enabled.

- `anon` and `authenticated`: column-level `SELECT` only for the dashboard-safe columns listed below
- `anon` and `authenticated`: no non-SELECT table privileges
- Backend collectors and server routes: write through `SUPABASE_SERVICE_ROLE_KEY`
- `service_role`: granted table privileges for backend-only operations; Supabase service role bypasses RLS

The hardened target policy set is one read policy:

```sql
CREATE POLICY "articles_public_select"
ON public.articles
FOR SELECT
TO anon, authenticated
USING (true);
```

Legacy anonymous write policies such as `"Enable insert for all users"` and `"Enable update for view_count"` must not exist after applying the hardening migration.

## 4. Dashboard Client Exposure

The dashboard client intentionally selects only these columns:

```text
id,title,agency,category,published_at,published_at_source,created_at,link,source_org,source_name,subcategory,analysis_result,view_count,star_rating
```

`content` is not fetched by the dashboard client. AI report generation continues to call `/api/report` with `articleId`; the server route loads `content` from Supabase with the service role key when needed.

The RLS hardening migration grants `anon` and `authenticated` column-level SELECT only for the same dashboard-safe set. `content`, `embedding`, and `is_trending` are not granted to public client roles.

## 5. `published_at_source`

- `source`: `published_at` came from the source page, RSS feed, or list item.
- `collected_fallback`: the source did not provide a usable publication time, so collection time was saved in `published_at`.
- `null`: legacy rows or rows saved before this marker existed.

Current UI behavior:

- `published_at_source = source`: display the KST time from `published_at`.
- `published_at_source = collected_fallback`: display collection time, preferring `created_at` then `published_at`.
- `published_at_source = null` and KST time is `00:00`: treat as legacy/date-only and display collection time fallback.

## 6. `analysis_result`

Typical payload:

```json
{
  "is_relevant": true,
  "importance_score": 3,
  "risk_level": "Medium",
  "summary": ["string"],
  "impact_analysis": "string",
  "action_items": ["string"],
  "keywords": ["string"],
  "filter_reason": "string",
  "detailed_report": "optional cached report",
  "report_generated_at": "optional ISO timestamp"
}
```

## 7. 내부 문서 Stage A (migration 추가, live 적용 미확인)

`db/migrations/202609100001_internal_documents.sql`은 `internal_documents`,
`internal_document_units`, `internal_document_jobs`, `internal_document_events`,
`internal_admin_limits`를 추가한다. 신규 테이블과 RPC는 service_role 전용이며
anon/authenticated/PUBLIC 권한은 회수한다. 문서별 조문 키가 유일하고,
삭제 완료 문서를 제외한 SHA-256과 문서 종류별 활성 버전이 유일하다.

`internal-documents` Storage bucket은 private이며 기존의 광범위 허용 정책이
있더라도 해당 bucket을 일반 클라이언트가 읽고 쓰지 못하도록 restrictive
정책을 추가한다. 내부 원문/추출문은 `articles.analysis_result`에 저장하지 않는다.

문서 상태는 uploading/queued/processing/review/active/retired/failed/
deleting/delete_failed/deleted이다. 검토 수정은 revision 충돌을 검사하고
활성화·교체는 트랜잭션으로 처리한다. worker는 lease token으로 완료를 확인한다.
세부 적용·복구 절차는 `docs/internal-documents-setup.md`에 기록한다.

## 8. 제재 분석 작업 (migration 추가, live 미적용)

`202609100002_sanction_inspections.sql`은 service_role 전용 `sanction_inspections`를 추가한다.
기사당 하나의 작업에 요청 ID, 활성 문서 revision 집합, lease, 비공개 초안을 저장한다.
상태는 queued/processing/needs_review/failed/stale이다. 관리자 enqueue와 worker claim/finish는
기존 문서 작업과 같은 advisory lock을 사용한다. 문서 버전 집합 변경 시 statement trigger가
결과를 지우고 lease를 무효화한다. 결과는 공개 `articles.analysis_result`에 저장하지 않는다.

## 9. 관리자 검토본·게시 snapshot (live 미적용)

`202609100003_inspection_publications.sql`은 분석 작업에 review_revision/review_draft를 추가하고
`sanction_publications`와 `inspection_review_events`를 생성한다. 모두 service_role 전용이다.
게시 snapshot에는 공개 DTO만 저장한다. 상태는 published/withdrawn이며 철회하면 report를 null로 지운다.
검토 저장·게시·철회는 revision과 활성 문서 버전을 검사하는 RPC로 처리한다.
재분석/문서 무효화는 검토본과 게시본도 지운다. 원문 인용 검사 및 DTO 검증은 관리자 서버에서
수행하고, 검사 때 읽은 revision과 같은 revision만 DB에서 게시할 수 있다.

## 10. 자동 분석·게시 (202609170001, 운영 적용 별도)
`sanction_inspections.automation_status`: none / pending / published / needs_attention / manual.
기존 작업은 none, 신규/명시적 재분석은 pending, 실패/규정 변경은 needs_attention.
자동 enqueue의 created_by는 null(시스템 작업), 관리자 실행은 기존 사용자 ID 유지.
`sanction_publications.publication_source`: manual / automatic; 기존 게시본은 manual.
자동 게시 RPC는 revision, 현재 규정 버전, pending, review_draft=null을 동시에 검사한다.
수동 save/publish/withdraw는 automation_status=manual로 전환하여 자동 덮어쓰기를 막는다.
source_key는 agency+examMgmtNo+emOpenSeq(없으면 원문 URL)이며 중복 URL의 게시 조회도 연결한다.
신규 RPC는 service_role 전용. 공개 API는 인증 후 정해진 DTO만 반환한다.

## 11. 직제규정 기반 분석 (202609180001)
문서 종류 organization과 internal_document_units.organization_names(JSONB 문자열 배열)을 추가한다. 원문 포함·중복·길이를 DB에서 검증하고, 검토 저장 후 조직명 없는 문서는 활성화하지 못한다. inspection_versions는 활성 organization만 반환한다. migration 적용 시 이전 기준 초안/게시본도 무효화한다. 공개 report.analysis_basis는 선택적 organization 리터럴이며 추정 표시를 보존한다.
