# Articles RLS Hardening 운영 적용 계획

## 목적

`public.articles`를 공개 대시보드 읽기 전용 테이블로 고정한다. 익명/인증 클라이언트는 조회만 가능하고, 수집기와 서버 route의 쓰기는 `SUPABASE_SERVICE_ROLE_KEY`를 통해 수행한다.

## 적용 대상 확인

- 저장소 `.env` / `web/.env.local`: `latgtrpmymqdlysgolat` 프로젝트를 가리킨다.
- Supabase CLI: 현재 프로젝트가 link되어 있지 않다.
- Supabase MCP: 현재 `termnezqjlqqaqqucyud` 프로젝트를 가리킨다. 이 프로젝트는 대상이 아니므로 운영 적용이나 live 정책 조회에 사용하지 않는다.
- 임시 Supabase CLI link로 확인한 live `public.articles` 정책:
  - `"Enable read access for all users"`: anon SELECT
  - `"Enable insert for all users"`: anon INSERT
  - `"Enable update for view_count"`: anon UPDATE with `using (true)` / `with check (true)`
- 임시 Supabase CLI query로 확인한 live table grants는 anon/authenticated에 SELECT 외 권한도 부여되어 있다. Migration은 table privilege까지 SELECT-only로 정리한다.

운영 적용 전에는 Supabase CLI를 `latgtrpmymqdlysgolat`에 link하거나, Supabase SQL Editor에서 같은 프로젝트인지 URL/project ref를 확인한다.

## 적용 전 확인할 Secret

- GitHub Actions v2 collector: `SUPABASE_SERVICE_ROLE_KEY_V2`
- GitHub Actions v2 collector fallback: `NEXT_PUBLIC_SUPABASE_ANON_KEY_V2`
- Vercel/server route: `SUPABASE_SERVICE_ROLE_KEY`
- Local backend fallback: `.env`의 `SUPABASE_ANON_KEY`

`SUPABASE_SERVICE_ROLE_KEY_V2`가 비어 있으면 collector는 코드상 anon fallback을 시도하지만, hardened RLS 적용 후 운영 DB write는 실패하는 것이 정상이다. 운영에서는 service role secret을 먼저 설정한다.

## 적용할 Migration

- 파일: `db/migrations/20260504145405_harden_articles_rls.sql`
- 데이터 영향: row `INSERT`, `UPDATE`, `DELETE` 없음
- 스키마 영향: `public.articles` RLS 활성화, 정책/권한 정리
- 제거 대상:
  - `"Enable insert for all users"`
  - `"Enable update for view_count"`
  - `anon`, `authenticated`, `PUBLIC`에 걸린 나머지 쓰기 정책
- 유지/생성 대상:
  - `"articles_public_select"` SELECT 정책 하나
  - `anon`, `authenticated`의 dashboard-safe 컬럼 SELECT 권한
  - `service_role`의 backend write 권한

## 기대 상태

- anon SELECT 가능
- anon `content` 컬럼 SELECT 불가
- anon INSERT 불가
- anon broad UPDATE 불가
- authenticated SELECT 가능
- authenticated `content` 컬럼 SELECT 불가
- authenticated INSERT/UPDATE/DELETE 불가
- service role/backend write 가능
- 대시보드 클라이언트는 `content` 컬럼을 조회하지 않음

## 적용 절차

1. GitHub/Vercel secret이 위 이름으로 설정되어 있는지 확인한다.
2. Supabase 대상 프로젝트가 `latgtrpmymqdlysgolat`인지 확인한다.
3. `db/migrations/20260504145405_harden_articles_rls.sql` 전체 SQL을 리뷰한다.
4. 운영 DB 적용 전 사용자에게 SQL 요약과 영향 범위를 다시 제시하고 확인을 받는다.
5. 확인 후 Supabase SQL Editor 또는 correct-project로 link된 Supabase CLI에서 migration을 적용한다.
6. 적용 후 `pg_policies` 기준으로 `articles_public_select`만 SELECT에 남고 anon/auth write 정책이 없는지 확인한다.
