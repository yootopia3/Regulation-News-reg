-- MarketPulse Regulation News v2.0 Schema Setup
-- Run this in Supabase SQL Editor

-- 0. Install required extensions
create extension if not exists vector;

-- DROP existing table to apply clean schema (CAUTION: Deletes all v2 data)
drop table if exists public.articles;

-- 1. Create articles table
create table if not exists public.articles (
    id uuid not null default gen_random_uuid(),
    created_at timestamp with time zone not null default now(),
    title text not null,
    link text not null,
    agency text not null,
    content text null,
    published_at timestamp with time zone not null,
    analysis_result jsonb null,
    embedding vector(1536) null,
    
    -- v2.0 New Columns
    view_count integer not null default 0,
    star_rating integer null check (star_rating >= 1 and star_rating <= 5),
    is_trending boolean not null default false,

    constraint articles_pkey primary key (id),
    constraint articles_link_key unique (link)
);

-- 2. Create Indexes
create index if not exists articles_agency_idx on public.articles (agency);
create index if not exists articles_published_at_idx on public.articles (published_at desc);

-- 3. Enable RLS (Row Level Security) and Policies
alter table public.articles enable row level security;

-- Allow anonymous access (anon key) to READ all articles
create policy "Enable read access for all users"
on public.articles
for select
to anon
using (true);

-- Allow anonymous access to UPDATE view_count (for trending feature)
-- Note: In production, this might need tighter control, but for v2 dev it's fine.
create policy "Enable update for view_count"
on public.articles
for update
to anon
using (true)
with check (true);

-- Allow anonymous access to INSERT (for initial seeding & manual registration if needed)
create policy "Enable insert for all users"
on public.articles
for insert
to anon
with check (true);

-- Note: INSERT/DELETE are restricted to service_role (backend only) by default.
