-- ============================================================================
-- Migration: Setup pg_cron for Materialized View Refresh
-- Date: 2026-01-10
-- Purpose: Automate refresh of all materialized views every 15 minutes
-- 
-- Usage Pattern: Scans run ~weekly, data is static most of the time
-- Refresh Interval: 15 minutes (simple, low overhead, reasonable freshness)
--
-- To adjust later:
--   SELECT cron.unschedule('refresh-all-materialized-views');
--   SELECT cron.schedule('refresh-all-materialized-views', '*/30 * * * *', ...);
-- ============================================================================

-- ============================================================================
-- STEP 1: Ensure pg_cron extension is enabled
-- Note: On Supabase, pg_cron is pre-installed. Just need to enable if not done.
-- ============================================================================
-- CREATE EXTENSION IF NOT EXISTS pg_cron;  -- Usually already enabled on Supabase

-- ============================================================================
-- STEP 2: Create modular refresh functions for flexibility
-- These allow refreshing subsets of MVs if needed in the future
-- ============================================================================

-- Lightweight MVs (fast, ~1-2 seconds total)
-- Used by: /programs, /dashboard, /scans
CREATE OR REPLACE FUNCTION public.refresh_lightweight_views() 
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_overview;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.asset_recon_counts;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.scan_subdomain_counts;
    
    RAISE NOTICE 'Lightweight materialized views refreshed at %', NOW();
END;
$$;

COMMENT ON FUNCTION public.refresh_lightweight_views() IS 
    'Refreshes fast MVs (~1-2s): asset_overview, asset_recon_counts, scan_subdomain_counts';

-- DNS MV (medium, ~2-3 seconds)
-- Used by: /dns page
CREATE OR REPLACE FUNCTION public.refresh_dns_views() 
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.subdomain_current_dns;
    
    RAISE NOTICE 'DNS materialized view refreshed at %', NOW();
END;
$$;

COMMENT ON FUNCTION public.refresh_dns_views() IS 
    'Refreshes DNS MV (~2-3s): subdomain_current_dns';

-- URL MVs (heavy, ~8-10 seconds total)
-- Used by: /urls page
CREATE OR REPLACE FUNCTION public.refresh_url_views() 
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_extensions;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_status_codes;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.url_top_sources;
    
    RAISE NOTICE 'URL materialized views refreshed at %', NOW();
END;
$$;

COMMENT ON FUNCTION public.refresh_url_views() IS 
    'Refreshes URL MVs (~8-10s): url_stats, url_top_extensions, url_top_status_codes, url_top_sources';

-- ============================================================================
-- STEP 3: Update the main refresh function to use modular functions
-- This is called by pg_cron
-- ============================================================================
CREATE OR REPLACE FUNCTION public.refresh_dashboard_views() 
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
BEGIN
    start_time := clock_timestamp();
    
    -- Refresh all MVs using modular functions
    PERFORM public.refresh_lightweight_views();
    PERFORM public.refresh_dns_views();
    PERFORM public.refresh_url_views();
    
    end_time := clock_timestamp();
    
    RAISE NOTICE 'All materialized views refreshed at % (duration: %)', 
        NOW(), 
        end_time - start_time;
END;
$$;

COMMENT ON FUNCTION public.refresh_dashboard_views() IS 
    'Refreshes ALL materialized views. Called by pg_cron every 15 minutes. Total duration: ~12-15 seconds.';

-- ============================================================================
-- STEP 4: Grant execute permissions on new functions
-- ============================================================================
GRANT EXECUTE ON FUNCTION public.refresh_lightweight_views() TO anon;
GRANT EXECUTE ON FUNCTION public.refresh_lightweight_views() TO authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_lightweight_views() TO service_role;

GRANT EXECUTE ON FUNCTION public.refresh_dns_views() TO anon;
GRANT EXECUTE ON FUNCTION public.refresh_dns_views() TO authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_dns_views() TO service_role;

GRANT EXECUTE ON FUNCTION public.refresh_url_views() TO anon;
GRANT EXECUTE ON FUNCTION public.refresh_url_views() TO authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_url_views() TO service_role;

-- ============================================================================
-- STEP 5: Remove any existing cron jobs for MV refresh (clean slate)
-- ============================================================================
DO $$
BEGIN
    -- Try to unschedule existing jobs (ignore errors if they don't exist)
    PERFORM cron.unschedule('refresh-dashboard-views');
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'No existing refresh-dashboard-views job to unschedule';
END;
$$;

DO $$
BEGIN
    PERFORM cron.unschedule('refresh-all-materialized-views');
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'No existing refresh-all-materialized-views job to unschedule';
END;
$$;

-- ============================================================================
-- STEP 6: Schedule the main refresh job - Every 15 minutes
-- ============================================================================
SELECT cron.schedule(
    'refresh-all-materialized-views',           -- Job name
    '*/15 * * * *',                             -- Every 15 minutes
    'SELECT public.refresh_dashboard_views();'  -- Command to run
);

-- ============================================================================
-- STEP 7: Verify the cron job was created
-- ============================================================================
DO $$
DECLARE
    job_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO job_count 
    FROM cron.job 
    WHERE jobname = 'refresh-all-materialized-views';
    
    IF job_count > 0 THEN
        RAISE NOTICE '✅ pg_cron job "refresh-all-materialized-views" created successfully';
        RAISE NOTICE '   Schedule: Every 15 minutes (*/15 * * * *)';
        RAISE NOTICE '   Command: SELECT public.refresh_dashboard_views();';
    ELSE
        RAISE WARNING '❌ Failed to create pg_cron job';
    END IF;
END;
$$;

-- ============================================================================
-- REFERENCE: Useful pg_cron commands
-- ============================================================================
-- 
-- View all scheduled jobs:
--   SELECT * FROM cron.job;
--
-- View job run history:
--   SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 20;
--
-- Unschedule a job:
--   SELECT cron.unschedule('refresh-all-materialized-views');
--
-- Change interval to 30 minutes:
--   SELECT cron.unschedule('refresh-all-materialized-views');
--   SELECT cron.schedule('refresh-all-materialized-views', '*/30 * * * *', 
--       'SELECT public.refresh_dashboard_views();');
--
-- Manually trigger a refresh:
--   SELECT public.refresh_dashboard_views();
--
-- Refresh only lightweight views:
--   SELECT public.refresh_lightweight_views();
--
-- Refresh only URL views:
--   SELECT public.refresh_url_views();
--
-- ============================================================================
