-- ============================================================================
-- Migration: Convert subdomain_current_dns to Materialized View
-- Date: 2026-01-10
-- Purpose: Fix intermittent 500 errors caused by statement timeouts
--          Regular VIEW requires GROUP BY on 258K+ records per query
--          Materialized VIEW caches the result for fast reads
-- ============================================================================

-- ============================================================================
-- STEP 1: Drop the existing regular VIEW
-- ============================================================================
DROP VIEW IF EXISTS public.subdomain_current_dns CASCADE;

-- ============================================================================
-- STEP 2: Create the MATERIALIZED VIEW with same structure
-- ============================================================================
CREATE MATERIALIZED VIEW public.subdomain_current_dns AS
SELECT 
    subdomain,
    parent_domain,
    array_agg(DISTINCT record_value ORDER BY record_value) FILTER (WHERE record_type = 'A') AS ipv4_addresses,
    array_agg(DISTINCT record_value ORDER BY record_value) FILTER (WHERE record_type = 'AAAA') AS ipv6_addresses,
    array_agg(DISTINCT record_value) FILTER (WHERE record_type = 'CNAME') AS cname_targets,
    array_agg(json_build_object('host', record_value, 'priority', COALESCE(priority, 0)) ORDER BY COALESCE(priority, 0)) FILTER (WHERE record_type = 'MX') AS mx_records,
    array_agg(DISTINCT record_value) FILTER (WHERE record_type = 'TXT') AS txt_records,
    max(resolved_at) AS last_resolved_at,
    max(ttl) AS max_ttl,
    string_agg(DISTINCT cloud_provider, ', ') FILTER (WHERE cloud_provider IS NOT NULL) AS cloud_providers,
    (array_agg(scan_job_id ORDER BY resolved_at DESC))[1] AS latest_scan_job_id,
    (array_agg(asset_id ORDER BY resolved_at DESC))[1] AS asset_id,
    count(*) AS total_records
FROM public.dns_records
GROUP BY subdomain, parent_domain
WITH DATA;

-- Set ownership
ALTER MATERIALIZED VIEW public.subdomain_current_dns OWNER TO postgres;

-- Add comment
COMMENT ON MATERIALIZED VIEW public.subdomain_current_dns IS 
    'Pre-computed DNS records grouped by subdomain. Refresh with: REFRESH MATERIALIZED VIEW CONCURRENTLY subdomain_current_dns;';

-- ============================================================================
-- STEP 3: Create indexes for fast queries
-- ============================================================================

-- UNIQUE index on (subdomain, parent_domain) - REQUIRED for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_mv_subdomain_dns_unique 
    ON public.subdomain_current_dns (subdomain, parent_domain);

-- Index for filtering by asset_id (common filter)
CREATE INDEX idx_mv_subdomain_dns_asset_id 
    ON public.subdomain_current_dns (asset_id);

-- Index for filtering by parent_domain (common filter)
CREATE INDEX idx_mv_subdomain_dns_parent_domain 
    ON public.subdomain_current_dns (parent_domain);

-- Index for ordering by last_resolved_at (pagination ordering)
CREATE INDEX idx_mv_subdomain_dns_last_resolved 
    ON public.subdomain_current_dns (last_resolved_at DESC);

-- Composite index for common query pattern: asset_id + ordering
CREATE INDEX idx_mv_subdomain_dns_asset_resolved 
    ON public.subdomain_current_dns (asset_id, last_resolved_at DESC);

-- Text search index for subdomain search (ilike queries)
-- Note: This uses pg_trgm extension for fast LIKE/ILIKE searches
-- Wrapped in exception handler in case pg_trgm is not available
DO $$
BEGIN
    -- Try to create the trigram index for fast ILIKE searches
    CREATE INDEX idx_mv_subdomain_dns_subdomain_trgm 
        ON public.subdomain_current_dns USING gin (subdomain gin_trgm_ops);
    RAISE NOTICE 'Created trigram index for fast subdomain searches';
EXCEPTION WHEN undefined_object THEN
    -- pg_trgm extension not available, create a regular btree index as fallback
    CREATE INDEX idx_mv_subdomain_dns_subdomain_btree 
        ON public.subdomain_current_dns (subdomain);
    RAISE NOTICE 'pg_trgm not available, created btree index instead (ILIKE searches will be slower)';
END;
$$;

-- ============================================================================
-- STEP 4: Grant permissions (same as other materialized views)
-- ============================================================================
GRANT ALL ON TABLE public.subdomain_current_dns TO anon;
GRANT ALL ON TABLE public.subdomain_current_dns TO authenticated;
GRANT ALL ON TABLE public.subdomain_current_dns TO service_role;

-- ============================================================================
-- STEP 5: Update refresh_dashboard_views function to include new MV
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

    RAISE NOTICE 'Dashboard materialized views refreshed at %', NOW();
END;
$$;

-- ============================================================================
-- STEP 6: Update refresh_views_for_asset function to include new MV
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

    RAISE NOTICE 'Views refreshed for asset % at %', p_asset_id, NOW();
END;
$$;

-- ============================================================================
-- VERIFICATION: Show row count and sample data
-- ============================================================================
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM public.subdomain_current_dns;
    RAISE NOTICE 'Materialized view subdomain_current_dns created with % rows', v_count;
END;
$$;
