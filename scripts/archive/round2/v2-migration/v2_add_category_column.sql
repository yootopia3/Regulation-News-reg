-- Migration: Add category column to articles table
-- Purpose: To distinguish between 'press_release' (default) and 'regulation_notice'.

-- 1. Add category column with default value 'press_release'
ALTER TABLE articles 
ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'press_release';

-- 2. Create index for faster filtering by category
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);

-- 3. Update comments/documentation (Optional)
COMMENT ON COLUMN articles.category IS 'Content type: press_release (default) or regulation_notice';

-- 4. Verification (Select to confirm)
-- SELECT id, title, category FROM articles LIMIT 5;
