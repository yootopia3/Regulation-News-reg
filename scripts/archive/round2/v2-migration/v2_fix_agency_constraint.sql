-- Fix for "violates check constraint articles_agency_check" error
-- We need to allow 'FSS_REG' and 'FSC_REG' in the agency column.

-- 1. Drop the old constraint
ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_agency_check;

-- 2. Add the updated constraint with new agencies
ALTER TABLE articles ADD CONSTRAINT articles_agency_check 
    CHECK (agency IN ('MOEF', 'FSC', 'FSS', 'BOK', 'FSS_REG', 'FSC_REG'));
