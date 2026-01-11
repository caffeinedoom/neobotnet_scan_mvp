-- ============================================================================
-- Migration: Performance Optimization - Materialized Views and Indexes
-- Created: 2026-01-10
-- Purpose: Improve dashboard query performance by:
--   1. Converting slow views to MATERIALIZED VIEWS
--   2. Adding composite indexes for common JOIN patterns
--   3. Creating refresh functions for materialized views
-- ============================================================================

-- ============================================================================
-- STEP 1: Drop existing regular views (we'll replace with materialized)
-- ============================================================================

DROP VIEW IF EXISTS "public"."asset_overview" CASCADE;
DROP VIEW IF EXISTS "public"."asset_recon_counts" CASCADE;
DROP VIEW IF EXISTS "public"."scan_subdomain_counts" CASCADE;

-- ============================================================================
-- STEP 2: Create MATERIALIZED VIEWS (store results, much faster reads)
-- ============================================================================

-- Materialized View: asset_overview
-- Pre-computed asset statistics with domain and subdomain counts
CREATE MATERIALIZED VIEW "public"."asset_overview" AS
SELECT 
    a.id,
    a.user_id,
    a.name,
    a.description,
    a.bug_bounty_url,
    a.is_active,
    a.priority,
    a.tags,
    a.created_at,
    a.updated_at,
    COUNT(DISTINCT ad.id) AS domain_count,
    COUNT(DISTINCT s.id) AS subdomain_count,
    COUNT(DISTINCT CASE WHEN ad.is_active = true THEN ad.id END) AS active_domain_count
FROM public.assets a
LEFT JOIN public.apex_domains ad ON a.id = ad.asset_id
LEFT JOIN public.asset_scan_jobs asj ON a.id = asj.asset_id
LEFT JOIN public.subdomains s ON asj.id = s.scan_job_id
GROUP BY a.id, a.user_id, a.name, a.description, a.bug_bounty_url, 
         a.is_active, a.priority, a.tags, a.created_at, a.updated_at
WITH DATA;

-- Index on materialized view for fast lookups
CREATE UNIQUE INDEX idx_mv_asset_overview_id ON public.asset_overview(id);
CREATE INDEX idx_mv_asset_overview_created_at ON public.asset_overview(created_at DESC);
CREATE INDEX idx_mv_asset_overview_is_active ON public.asset_overview(is_active) WHERE is_active = true;

COMMENT ON MATERIALIZED VIEW public.asset_overview IS 
'Pre-computed asset statistics. Refresh with: REFRESH MATERIALIZED VIEW CONCURRENTLY asset_overview;';


-- Materialized View: asset_recon_counts
-- Pre-computed reconnaissance counts per asset (probes, DNS, URLs)
CREATE MATERIALIZED VIEW "public"."asset_recon_counts" AS
SELECT 
    a.id AS asset_id,
    COALESCE(hp.probe_count, 0) AS probe_count,
    COALESCE(dr.dns_count, 0) AS dns_count,
    COALESCE(u.url_count, 0) AS url_count
FROM public.assets a
LEFT JOIN (
    SELECT asset_id, COUNT(*) AS probe_count
    FROM public.http_probes
    GROUP BY asset_id
) hp ON a.id = hp.asset_id
LEFT JOIN (
    SELECT asset_id, COUNT(*) AS dns_count
    FROM public.dns_records
    GROUP BY asset_id
) dr ON a.id = dr.asset_id
LEFT JOIN (
    SELECT asset_id, COUNT(*) AS url_count
    FROM public.urls
    GROUP BY asset_id
) u ON a.id = u.asset_id
WITH DATA;

-- Index on materialized view
CREATE UNIQUE INDEX idx_mv_asset_recon_counts_asset_id ON public.asset_recon_counts(asset_id);

COMMENT ON MATERIALIZED VIEW public.asset_recon_counts IS 
'Pre-computed reconnaissance counts per asset. Refresh with: REFRESH MATERIALIZED VIEW CONCURRENTLY asset_recon_counts;';


-- Materialized View: scan_subdomain_counts
-- Pre-computed subdomain counts per scan job
CREATE MATERIALIZED VIEW "public"."scan_subdomain_counts" AS
SELECT 
    scan_job_id,
    COUNT(*) AS subdomain_count
FROM public.subdomains
WHERE scan_job_id IS NOT NULL
GROUP BY scan_job_id
WITH DATA;

-- Index on materialized view
CREATE UNIQUE INDEX idx_mv_scan_subdomain_counts_job_id ON public.scan_subdomain_counts(scan_job_id);

COMMENT ON MATERIALIZED VIEW public.scan_subdomain_counts IS 
'Pre-computed subdomain counts per scan job. Refresh with: REFRESH MATERIALIZED VIEW CONCURRENTLY scan_subdomain_counts;';


-- ============================================================================
-- STEP 3: Create refresh functions for materialized views
-- ============================================================================

-- Function to refresh all dashboard materialized views
CREATE OR REPLACE FUNCTION public.refresh_dashboard_views()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Use CONCURRENTLY to allow reads during refresh (requires unique index)
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_overview;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_recon_counts;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.scan_subdomain_counts;
    
    RAISE NOTICE 'Dashboard materialized views refreshed at %', NOW();
END;
$$;

COMMENT ON FUNCTION public.refresh_dashboard_views() IS 
'Refreshes all dashboard materialized views concurrently. Safe to call during normal operations.';


-- Function to refresh views after a scan completes
-- This should be called by the scan completion webhook/trigger
CREATE OR REPLACE FUNCTION public.refresh_views_for_asset(p_asset_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- For single asset updates, we still need to refresh the full views
    -- But we can be selective about which ones to refresh
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_overview;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_recon_counts;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.scan_subdomain_counts;
    
    RAISE NOTICE 'Views refreshed for asset % at %', p_asset_id, NOW();
END;
$$;


-- ============================================================================
-- STEP 4: Add additional composite indexes for common query patterns
-- ============================================================================

-- Index for asset_scan_jobs ordered by created_at (used in recon-data LIMIT 20)
CREATE INDEX IF NOT EXISTS idx_asset_scan_jobs_asset_created_desc 
ON public.asset_scan_jobs(asset_id, created_at DESC);

-- Index for subdomains count by scan_job_id (used in scan_subdomain_counts view)
CREATE INDEX IF NOT EXISTS idx_subdomains_scan_job_count 
ON public.subdomains(scan_job_id) 
WHERE scan_job_id IS NOT NULL;

-- Index for http_probes count by asset_id (used in asset_recon_counts view)
CREATE INDEX IF NOT EXISTS idx_http_probes_asset_count 
ON public.http_probes(asset_id);

-- Index for dns_records count by asset_id (used in asset_recon_counts view)
CREATE INDEX IF NOT EXISTS idx_dns_records_asset_count 
ON public.dns_records(asset_id);

-- Index for urls count by asset_id (used in asset_recon_counts view)
CREATE INDEX IF NOT EXISTS idx_urls_asset_count 
ON public.urls(asset_id);


-- ============================================================================
-- STEP 5: Grant permissions on new materialized views
-- ============================================================================

GRANT SELECT ON public.asset_overview TO anon, authenticated, service_role;
GRANT SELECT ON public.asset_recon_counts TO anon, authenticated, service_role;
GRANT SELECT ON public.scan_subdomain_counts TO anon, authenticated, service_role;

-- Grant execute on refresh functions to service_role only
GRANT EXECUTE ON FUNCTION public.refresh_dashboard_views() TO service_role;
GRANT EXECUTE ON FUNCTION public.refresh_views_for_asset(UUID) TO service_role;


-- ============================================================================
-- STEP 6: Create a scheduled job hint (for pg_cron or application-level)
-- ============================================================================

-- NOTE: If using pg_cron extension, you can schedule automatic refreshes:
-- SELECT cron.schedule('refresh-dashboard-views', '*/5 * * * *', 'SELECT public.refresh_dashboard_views();');
-- This would refresh every 5 minutes.

-- Alternative: Call refresh_dashboard_views() from your application:
-- - After scan completion
-- - On a scheduled task (every 5-10 minutes)
-- - On-demand via admin API

COMMENT ON SCHEMA public IS 
'Standard public schema with materialized views for dashboard performance. 
Run SELECT public.refresh_dashboard_views() periodically or after scans complete.';
