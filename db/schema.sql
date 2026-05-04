-- public.articles as-built reference schema.
-- 기존 운영 DB에는 이 파일을 직접 적용하지 말고 db/migrations를 검토해 적용한다.
-- 데이터 row를 변경하지 않는 참조 스키마로 유지한다.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.articles (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    title text NOT NULL,
    link text NOT NULL,
    agency text NOT NULL,
    content text,
    published_at timestamp with time zone NOT NULL,
    published_at_source text,
    analysis_result jsonb,
    embedding vector(1536),
    view_count integer NOT NULL DEFAULT 0,
    star_rating integer CHECK (star_rating >= 1 AND star_rating <= 5),
    is_trending boolean NOT NULL DEFAULT false,
    category character varying(50) DEFAULT 'press_release',

    CONSTRAINT articles_pkey PRIMARY KEY (id),
    CONSTRAINT articles_link_key UNIQUE (link),
    CONSTRAINT articles_agency_check CHECK (
        agency IN (
            'FSC',
            'FSS',
            'MOEF',
            'BOK',
            'FSS_REG',
            'FSC_REG',
            'FSS_REG_INFO',
            'FSS_SANCTION',
            'FSS_MGMT_NOTICE',
            'MAFRA'
        )
    ),
    CONSTRAINT articles_published_at_source_check CHECK (
        published_at_source IS NULL
        OR published_at_source IN ('source', 'collected_fallback')
    )
);

COMMENT ON TABLE public.articles IS 'Stores government press releases, notices, source content, and analysis results.';
COMMENT ON COLUMN public.articles.category IS 'Content type used by the dashboard: press_release, regulation_notice, or sanction_notice.';
COMMENT ON COLUMN public.articles.content IS 'Original source body for backend/report generation. The dashboard client must not select this column.';
COMMENT ON COLUMN public.articles.analysis_result IS 'JSONB structure containing summaries, scores, keywords, cached reports, and related analysis fields.';
COMMENT ON COLUMN public.articles.published_at_source IS 'source = 실제 발행시각, collected_fallback = 수집시각 fallback';
COMMENT ON COLUMN public.articles.embedding IS 'Legacy nullable pgvector placeholder; current application code does not write embeddings.';

CREATE INDEX IF NOT EXISTS articles_agency_idx
ON public.articles (agency);

CREATE INDEX IF NOT EXISTS articles_published_at_idx
ON public.articles (published_at DESC);

CREATE INDEX IF NOT EXISTS idx_articles_category
ON public.articles (category);

ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Enable insert for all users" ON public.articles;
DROP POLICY IF EXISTS "Enable update for view_count" ON public.articles;

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
