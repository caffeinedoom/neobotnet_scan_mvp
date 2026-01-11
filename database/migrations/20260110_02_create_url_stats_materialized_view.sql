-- ============================================================================
-- Migration: Create URL Stats Materialized View
-- Date: 2026-01-10
-- Purpose: Fix slow /urls and /urls/stats endpoints
--          Current: 6+ sequential queries on 362K row table (~4 seconds)
--          After: Single query on pre-computed MV (~100ms)
-- ============================================================================

-- ============================================================================
-- STEP 1: Create url_stats Materialized View
-- Pre-computes all the counts that the stats endpoint needs
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS public.url_stats AS
SELECT 
    COUNT(*) AS total_urls,
    COUNT(*) FILTER (WHERE is_alive = true) AS alive_urls,
    COUNT(*) FILTER (WHERE is_alive = false) AS dead_urls,
    COUNT(*) FILTER (WHERE resolved_at IS NULL) AS pending_urls,
    COUNT(*) FILTER (WHERE has_params = true) AS urls_with_params,
    COUNT(DISTINCT domain) AS unique_domains,
    COUNT(DISTINCT asset_id) AS unique_assets,
    -- Status code distribution
    COUNT(*) FILTER (WHERE status_code >= 200 AND status_code < 300) AS status_2xx,
    COUNT(*) FILTER (WHERE status_code >= 300 AND status_code < 400) AS status_3xx,
    COUNT(*) FILTER (WHERE status_code >= 400 AND status_code < 500) AS status_4xx,
    COUNT(*) FILTER (WHERE status_code >= 500 AND status_code < 600) AS status_5xx
FROM public.urls
WITH DATA;

-- Set ownership
ALTER MATERIALIZED VIEW public.url_stats OWNER TO postgres;

-- Add comment
COMMENT ON MATERIALIZED VIEW public.url_stats IS 
    'Pre-computed URL statistics. Refresh with: REFRESH MATERIALIZED VIEW CONCURRENTLY url_stats;';

-- ============================================================================
-- STEP 2: Create unique index for CONCURRENTLY refresh
-- Since this is a single-row aggregate, we use a constant column
-- ============================================================================
-- Create a unique index (required for REFRESH CONCURRENTLY)
-- We add a dummy constant since this is a single-row view
CREATE UNIQUE INDEX idx_mv_url_stats_unique 
    ON public.url_stats ((1));

-- ============================================================================
-- STEP 3: Create url_top_extensions Materialized View
-- Top file extensions for dropdown filters
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS public.url_top_extensions AS
SELECT 
    file_extension,
    COUNT(*) AS count
FROM public.urls
WHERE file_extension IS NOT NULL
GROUP BY file_extension
ORDER BY COUNT(*) DESC
LIMIT 50
WITH DATA;

ALTER MATERIALIZED VIEW public.url_top_extensions OWNER TO postgres;

CREATE UNIQUE INDEX idx_mv_url_top_extensions_unique 
    ON public.url_top_extensions (file_extension);

-- ============================================================================
-- STEP 4: Create url_top_status_codes Materialized View
-- Status code distribution
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS public.url_top_status_codes AS
SELECT 
    status_code,
    COUNT(*) AS count
FROM public.urls
WHERE status_code IS NOT NULL
GROUP BY status_code
ORDER BY COUNT(*) DESC
LIMIT 20
WITH DATA;

ALTER MATERIALIZED VIEW public.url_top_status_codes OWNER TO postgres;

CREATE UNIQUE INDEX idx_mv_url_top_status_codes_unique 
    ON public.url_top_status_codes (status_code);

-- ============================================================================
-- STEP 5: Create url_top_sources Materialized View
-- Top discovery sources (requires JSONB array expansion)
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS public.url_top_sources AS
SELECT 
    source,
    COUNT(*) AS count
FROM public.urls,
    jsonb_array_elements_text(sources) AS source
GROUP BY source
ORDER BY COUNT(*) DESC
LIMIT 20
WITH DATA;

ALTER MATERIALIZED VIEW public.url_top_sources OWNER TO postgres;

CREATE UNIQUE INDEX idx_mv_url_top_sources_unique 
    ON public.url_top_sources (source);

-- ============================================================================
-- STEP 6: Grant permissions (same as other materialized views)
-- ============================================================================
GRANT ALL ON TABLE public.url_stats TO anon;
GRANT ALL ON TABLE public.url_stats TO authenticated;
GRANT ALL ON TABLE public.url_stats TO service_role;

GRANT ALL ON TABLE public.url_top_extensions TO anon;
GRANT ALL ON TABLE public.url_top_extensions TO authenticated;
GRANT ALL ON TABLE public.url_top_extensions TO service_role;

GRANT ALL ON TABLE public.url_top_status_codes TO anon;
GRANT ALL ON TABLE public.url_top_status_codes TO authenticated;
GRANT ALL ON TABLE public.url_top_status_codes TO service_role;

GRANT ALL ON TABLE public.url_top_sources TO anon;
GRANT ALL ON TABLE public.url_top_sources TO authenticated;
GRANT ALL ON TABLE public.url_top_sources TO service_role;

-- ============================================================================
-- STEP 7: Update refresh_dashboard_views function to include URL MVs
-- ============================================================================
CREATE OR REPLACE FUNCTION public.refresh_dashboard_views() 
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
    -- Use CONCURRENTLY to allow reads during refresh (requires unique index)
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_overview;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_recon_counts;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.scan_subdomain_counts;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.subdomain_current_dns;
    
    -- URL stats views
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_extensions;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_status_codes;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_sources;

    RAISE NOTICE 'Dashboard materialized views refreshed at %', NOW();
END;
$$;

-- ============================================================================
-- STEP 8: Update refresh_views_for_asset function to include URL MVs
-- ============================================================================
CREATE OR REPLACE FUNCTION public.refresh_views_for_asset(p_asset_id uuid) 
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
    -- For single asset updates, we still need to refresh the full views
    -- But we can be selective about which ones to refresh
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_overview;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_recon_counts;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.scan_subdomain_counts;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.subdomain_current_dns;
    
    -- URL stats views
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_extensions;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_status_codes;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_sources;

    RAISE NOTICE 'Views refreshed for asset % at %', p_asset_id, NOW();
END;
$$;

-- ============================================================================
-- STEP 9: Add trigram index for faster ILIKE searches (if pg_trgm available)
-- ============================================================================
DO $$
BEGIN
    -- Try to create the trigram index for fast ILIKE searches on domain
    CREATE INDEX idx_urls_domain_trgm 
        ON public.urls USING gin (domain gin_trgm_ops);
    RAISE NOTICE 'Created trigram index for fast domain searches';
EXCEPTION WHEN undefined_object THEN
    -- pg_trgm extension not available, skip
    RAISE NOTICE 'pg_trgm not available, skipping trigram index for domain';
END;
$$;

DO $$
BEGIN
    -- Try to create the trigram index for fast ILIKE searches on url
    CREATE INDEX idx_urls_url_trgm 
        ON public.urls USING gin (url gin_trgm_ops);
    RAISE NOTICE 'Created trigram index for fast URL searches';
EXCEPTION WHEN undefined_object THEN
    -- pg_trgm extension not available, skip
    RAISE NOTICE 'pg_trgm not available, skipping trigram index for url';
END;
$$;

-- ============================================================================
-- VERIFICATION: Show row counts
-- ============================================================================
DO $$
DECLARE
    v_stats_count INTEGER;
    v_ext_count INTEGER;
    v_status_count INTEGER;
    v_sources_count INTEGER;
BEGIN
    SELECT 1 INTO v_stats_count FROM public.url_stats;
    SELECT COUNT(*) INTO v_ext_count FROM public.url_top_extensions;
    SELECT COUNT(*) INTO v_status_count FROM public.url_top_status_codes;
    SELECT COUNT(*) INTO v_sources_count FROM public.url_top_sources;
    
    RAISE NOTICE 'URL Materialized Views created:';
    RAISE NOTICE '  - url_stats: 1 row (aggregate)';
    RAISE NOTICE '  - url_top_extensions: % rows', v_ext_count;
    RAISE NOTICE '  - url_top_status_codes: % rows', v_status_count;
    RAISE NOTICE '  - url_top_sources: % rows', v_sources_count;
END;
$$;
