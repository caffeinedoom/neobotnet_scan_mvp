-- ============================================================================
-- Migration: Add composite index for domain + first_discovered_at queries
-- Date: 2026-01-13
-- 
-- Problem: Queries like `domain=eq.wise.com ORDER BY first_discovered_at DESC`
-- timeout when there are thousands of matching rows (7K-14K+) because:
--   1. idx_urls_domain finds matching rows (fast)
--   2. PostgreSQL must then sort 14K+ rows by first_discovered_at (slow!)
--
-- Solution: Composite index allows both filter AND sort in one index scan.
-- ============================================================================

-- Create composite index for domain + first_discovered_at queries
-- This supports: WHERE domain = 'x' ORDER BY first_discovered_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_urls_domain_discovered 
ON public.urls (domain, first_discovered_at DESC);

-- Also create index for parent_domain pattern matching with ordering
-- This helps queries like: WHERE domain ILIKE '%.wise.com' ORDER BY first_discovered_at DESC
-- Note: For ILIKE with leading wildcard, a trigram index would be even better,
-- but this composite index still helps with the sort phase after filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_urls_domain_text_pattern_discovered
ON public.urls (domain text_pattern_ops, first_discovered_at DESC);

-- ============================================================================
-- Verification
-- ============================================================================
DO $$
DECLARE
    idx_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO idx_count 
    FROM pg_indexes 
    WHERE tablename = 'urls' 
    AND indexname IN ('idx_urls_domain_discovered', 'idx_urls_domain_text_pattern_discovered');
    
    IF idx_count >= 1 THEN
        RAISE NOTICE '✅ Domain + discovered_at composite index created successfully';
        RAISE NOTICE '   Queries like "domain=wise.com ORDER BY first_discovered_at" should now be fast';
    ELSE
        RAISE WARNING '❌ Index creation may have failed';
    END IF;
END;
$$;

-- ============================================================================
-- Expected performance improvement:
--   Before: 8+ seconds (timeout) for domains with 7K-14K URLs
--   After:  < 500ms
--
-- Test after applying:
--   SELECT id, domain FROM urls 
--   WHERE domain = 'wise.com' 
--   ORDER BY first_discovered_at DESC 
--   LIMIT 100;
-- ============================================================================
