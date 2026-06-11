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
