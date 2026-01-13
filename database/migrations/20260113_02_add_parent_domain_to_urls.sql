-- ============================================================================
-- Migration: Add parent_domain column to urls table
-- Date: 2026-01-13
-- 
-- Problem: Filtering URLs by parent_domain uses ILIKE '%.wise.com' which
-- requires full table scan and can't use indexes efficiently.
--
-- Solution: Add denormalized parent_domain column (apex domain) that can be
-- indexed and queried with exact match.
--
-- Example:
--   domain: "api.foo.wise.com"
--   parent_domain: "wise.com" (derived from apex_domains table)
-- ============================================================================

-- ============================================================================
-- STEP 1: Add parent_domain column (nullable initially for migration)
-- ============================================================================
ALTER TABLE public.urls 
ADD COLUMN IF NOT EXISTS parent_domain TEXT;

-- Add comment explaining the column
COMMENT ON COLUMN public.urls.parent_domain IS 
    'Apex domain for this URL (e.g., wise.com). Derived from apex_domains table. Enables fast filtering without ILIKE.';

-- ============================================================================
-- STEP 2: Populate parent_domain from apex_domains table
-- 
-- Logic: For each URL, find the matching apex_domain where:
--   - Same asset_id AND
--   - URL's domain equals apex_domain OR ends with '.apex_domain'
-- ============================================================================
UPDATE public.urls u
SET parent_domain = ad.domain
FROM public.apex_domains ad
WHERE u.asset_id = ad.asset_id
  AND u.parent_domain IS NULL  -- Only update rows not yet set
  AND (
    u.domain = ad.domain 
    OR u.domain LIKE '%.' || ad.domain
  );

-- ============================================================================
-- STEP 3: Handle any URLs that couldn't be matched
-- Fall back to extracting apex domain from the URL's domain field
-- This handles edge cases where apex_domains might not have the entry
-- ============================================================================
-- For unmatched URLs, use the domain as-is (best effort)
-- In practice, most URLs should match via apex_domains
UPDATE public.urls
SET parent_domain = domain
WHERE parent_domain IS NULL;

-- ============================================================================
-- STEP 4: Create composite index for fast filtering + ordering
-- This is the key performance improvement
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_urls_parent_domain_discovered 
ON public.urls (parent_domain, first_discovered_at DESC);

-- Also create a simple B-tree index on parent_domain for equality checks
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_urls_parent_domain 
ON public.urls (parent_domain);

-- ============================================================================
-- STEP 5: Create trigger to auto-set parent_domain on INSERT
-- This ensures new URLs automatically get parent_domain set
-- ============================================================================

-- Function to derive parent_domain from domain and apex_domains table
CREATE OR REPLACE FUNCTION public.set_url_parent_domain()
RETURNS TRIGGER AS $$
DECLARE
    matched_domain TEXT;
BEGIN
    -- Try to find matching apex_domain for this URL
    SELECT ad.domain INTO matched_domain
    FROM public.apex_domains ad
    WHERE ad.asset_id = NEW.asset_id
      AND (NEW.domain = ad.domain OR NEW.domain LIKE '%.' || ad.domain)
    LIMIT 1;
    
    -- Set parent_domain to matched apex_domain or fall back to domain
    IF matched_domain IS NOT NULL THEN
        NEW.parent_domain := matched_domain;
    ELSE
        -- Fallback: use the domain as-is (edge case)
        NEW.parent_domain := NEW.domain;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for INSERT (only if parent_domain is not already set)
DROP TRIGGER IF EXISTS trg_set_url_parent_domain ON public.urls;
CREATE TRIGGER trg_set_url_parent_domain
    BEFORE INSERT ON public.urls
    FOR EACH ROW
    WHEN (NEW.parent_domain IS NULL)
    EXECUTE FUNCTION public.set_url_parent_domain();

COMMENT ON FUNCTION public.set_url_parent_domain() IS 
    'Automatically sets parent_domain for new URLs by matching with apex_domains table';

-- ============================================================================
-- STEP 6: Add NOT NULL constraint (optional - do after verifying data)
-- Uncomment if you want to enforce non-null parent_domain
-- ============================================================================
-- ALTER TABLE public.urls 
-- ALTER COLUMN parent_domain SET NOT NULL;

-- ============================================================================
-- STEP 7: Update url_stats materialized view to include parent_domain stats
-- (Optional - can be done later if needed)
-- ============================================================================

-- ============================================================================
-- Verification
-- ============================================================================
DO $$
DECLARE
    total_urls INTEGER;
    urls_with_parent_domain INTEGER;
    null_parent_domain INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_urls FROM public.urls;
    SELECT COUNT(*) INTO urls_with_parent_domain FROM public.urls WHERE parent_domain IS NOT NULL;
    SELECT COUNT(*) INTO null_parent_domain FROM public.urls WHERE parent_domain IS NULL;
    
    RAISE NOTICE '=== Migration Results ===';
    RAISE NOTICE 'Total URLs: %', total_urls;
    RAISE NOTICE 'URLs with parent_domain set: %', urls_with_parent_domain;
    RAISE NOTICE 'URLs with NULL parent_domain: %', null_parent_domain;
    
    IF null_parent_domain = 0 THEN
        RAISE NOTICE '✅ All URLs have parent_domain set!';
    ELSE
        RAISE WARNING '⚠️  % URLs still have NULL parent_domain', null_parent_domain;
    END IF;
END;
$$;

-- ============================================================================
-- Test query (run after migration to verify performance):
--
--   EXPLAIN ANALYZE
--   SELECT id, domain, parent_domain FROM urls 
--   WHERE parent_domain = 'wise.com' 
--   ORDER BY first_discovered_at DESC 
--   LIMIT 100;
--
-- Expected: Index Scan using idx_urls_parent_domain_discovered
-- ============================================================================
