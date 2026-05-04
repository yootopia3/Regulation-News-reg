-- Harden public.articles RLS and table grants.
-- Data-safe migration: changes policies/privileges only and does not modify rows.

ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;

-- Remove known legacy anonymous write policies.
DROP POLICY IF EXISTS "Enable insert for all users" ON public.articles;
DROP POLICY IF EXISTS "Enable update for view_count" ON public.articles;

-- Remove any remaining write policies that apply to anon/authenticated/PUBLIC.
DO $$
DECLARE
    policy_record record;
BEGIN
    FOR policy_record IN
        SELECT pol.polname
        FROM pg_policy pol
        JOIN pg_class cls ON cls.oid = pol.polrelid
        JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
        WHERE nsp.nspname = 'public'
          AND cls.relname = 'articles'
          AND pol.polcmd IN ('a', 'w', 'd', '*')
          AND (
              0 = ANY(pol.polroles)
              OR EXISTS (
                  SELECT 1
                  FROM unnest(pol.polroles) AS role_oid(role_id)
                  JOIN pg_roles rol ON rol.oid = role_oid.role_id
                  WHERE rol.rolname IN ('anon', 'authenticated')
              )
          )
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.articles', policy_record.polname);
    END LOOP;
END $$;

-- Keep exactly one public read policy for the dashboard.
DO $$
DECLARE
    policy_record record;
BEGIN
    FOR policy_record IN
        SELECT pol.polname
        FROM pg_policy pol
        JOIN pg_class cls ON cls.oid = pol.polrelid
        JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
        WHERE nsp.nspname = 'public'
          AND cls.relname = 'articles'
          AND pol.polcmd = 'r'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.articles', policy_record.polname);
    END LOOP;
END $$;

CREATE POLICY "articles_public_select"
ON public.articles
FOR SELECT
TO anon, authenticated
USING (true);

-- Table privileges mirror the RLS model: public clients read only;
-- backend collectors and server routes use the service role for writes.
GRANT USAGE ON SCHEMA public TO anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.articles FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TABLE public.articles FROM anon, authenticated;
GRANT SELECT (
    id,
    title,
    agency,
    category,
    published_at,
    published_at_source,
    created_at,
    link,
    analysis_result,
    view_count,
    star_rating
) ON TABLE public.articles TO anon, authenticated;
GRANT ALL PRIVILEGES ON TABLE public.articles TO service_role;
