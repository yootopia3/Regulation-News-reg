ALTER TABLE public.articles
    ADD COLUMN IF NOT EXISTS published_at_source text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'articles_published_at_source_check'
          AND conrelid = 'public.articles'::regclass
    ) THEN
        ALTER TABLE public.articles
            ADD CONSTRAINT articles_published_at_source_check
            CHECK (
                published_at_source IS NULL
                OR published_at_source IN ('source', 'collected_fallback')
            );
    END IF;
END $$;

COMMENT ON COLUMN public.articles.published_at_source IS 'source = 실제 발행시각, collected_fallback = 수집시각 fallback';
