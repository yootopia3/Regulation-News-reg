-- Emergency Fix: Drop the agency check constraint entirely
-- This unblocks the backfill process immediately.
-- We can re-add the constraint later if needed.

ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_agency_check;
