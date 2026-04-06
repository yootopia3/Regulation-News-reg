-- Force Fix for "articles_agency_check" violation
-- This script cleans up any invalid agency data before applying the rule.

-- 1. Cleaning Step: Update any unknown agency to 'FSC' (Safety Net)
--    This ensures all rows conform to the allowed list.
UPDATE articles 
SET agency = 'FSC' 
WHERE agency NOT IN ('MOEF', 'FSC', 'FSS', 'BOK', 'FSS_REG', 'FSC_REG');

-- 2. Drop the old constraint
ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_agency_check;

-- 3. Add the updated constraint
ALTER TABLE articles ADD CONSTRAINT articles_agency_check 
    CHECK (agency IN ('MOEF', 'FSC', 'FSS', 'BOK', 'FSS_REG', 'FSC_REG'));
