-- Add Korea Federation of Banks (KFB) metadata and dedup support.

ALTER TABLE public.articles
ADD COLUMN IF NOT EXISTS source_org text,
ADD COLUMN IF NOT EXISTS source_name text,
ADD COLUMN IF NOT EXISTS subcategory text,
ADD COLUMN IF NOT EXISTS dedup_key text;

UPDATE public.articles
SET dedup_key = COALESCE(dedup_key, agency || ':' || link)
WHERE dedup_key IS NULL
  AND agency IS NOT NULL
  AND link IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'articles_dedup_key_key'
    ) THEN
        ALTER TABLE public.articles
        ADD CONSTRAINT articles_dedup_key_key UNIQUE (dedup_key);
    END IF;
END $$;

ALTER TABLE public.articles
DROP CONSTRAINT IF EXISTS articles_agency_check;

ALTER TABLE public.articles
ADD CONSTRAINT articles_agency_check CHECK (
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
        'MAFRA',
        'KFB'
    )
);

GRANT SELECT (
    id,
    title,
    agency,
    category,
    published_at,
    published_at_source,
    created_at,
    link,
    source_org,
    source_name,
    subcategory,
    analysis_result,
    view_count,
    star_rating
) ON TABLE public.articles TO anon, authenticated;
