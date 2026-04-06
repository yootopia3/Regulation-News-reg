-- Enable the pg_cron extension if needed for scheduling within DB (optional, but good to have)
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Create the articles table
CREATE TABLE IF NOT EXISTS public.articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency TEXT NOT NULL CHECK (agency IN ('FSC', 'FSS', 'MOEF', 'BOK', 'MAFRA')),
    title TEXT NOT NULL,
    link TEXT NOT NULL UNIQUE,
    published_at TIMESTAMPTZ NOT NULL,
    content TEXT, -- Original content from the scraper
    analysis_result JSONB, -- Gemini analysis result
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 1. Enable Row Level Security (RLS)
ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;

-- Create policy to allow read access (SELECT) for everyone (anon and authenticated)
-- This is for the public Web Dashboard.
CREATE POLICY "Allow public read access"
ON public.articles
FOR SELECT
TO anon, authenticated
USING (true);

-- Create policy to allow insert/update only for service_role (backend)
-- Ideally, we don't grant write access to anon/authenticated.
-- The backend script will use the service_role key or a specific user.
-- For now, implicit denial for anon/authenticated on INSERT/UPDATE/DELETE applies.

-- 2. Indexing for performance
-- Index for sorting by latest news
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON public.articles (published_at DESC);

-- Index for filtering by agency
CREATE INDEX IF NOT EXISTS idx_articles_agency ON public.articles (agency);

-- Composite index might be useful if we frequently query "latest news by agency"
CREATE INDEX IF NOT EXISTS idx_articles_agency_published_at ON public.articles (agency, published_at DESC);

COMMENT ON TABLE public.articles IS 'Stores government press releases and Gemini analysis results.';
COMMENT ON COLUMN public.articles.analysis_result IS 'JSONB structure containing summary, impact analysis, etc.';
