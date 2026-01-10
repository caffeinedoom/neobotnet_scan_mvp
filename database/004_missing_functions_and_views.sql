-- ============================================================================
-- Migration: Add Missing Functions and Optimize Views
-- Created: 2026-01-10
-- Purpose: Fix 500 errors by:
--   1. Adding missing increment_url_quota RPC function
--   2. Making user_usage_overview more resilient (LEFT JOIN)
--   3. Adding index for apex_domain_overview performance
-- ============================================================================

-- ============================================================================
-- STEP 1: Add missing increment_url_quota function
-- Called by tier_check.py for atomically incrementing URL view count
-- ============================================================================

CREATE OR REPLACE FUNCTION public.increment_url_quota(
    p_user_id UUID,
    p_count INTEGER
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Ensure user has a usage record first
    INSERT INTO public.user_usage (user_id, urls_viewed_count)
    VALUES (p_user_id, 0)
    ON CONFLICT (user_id) DO NOTHING;
    
    -- Atomically increment the count
    UPDATE public.user_usage
    SET urls_viewed_count = COALESCE(urls_viewed_count, 0) + p_count,
        updated_at = NOW()
    WHERE user_id = p_user_id;
END;
$$;

ALTER FUNCTION public.increment_url_quota(UUID, INTEGER) OWNER TO postgres;

COMMENT ON FUNCTION public.increment_url_quota(UUID, INTEGER) IS 
'Atomically increments the urls_viewed_count for a user. Creates user_usage record if needed.';

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.increment_url_quota(UUID, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION public.increment_url_quota(UUID, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION public.increment_url_quota(UUID, INTEGER) TO service_role;


-- ============================================================================
-- STEP 2: Make user_usage_overview more resilient with LEFT JOIN
-- Current INNER JOIN causes empty results when user_quotas is missing
-- ============================================================================

DROP VIEW IF EXISTS public.user_usage_overview;

CREATE OR REPLACE VIEW public.user_usage_overview AS
SELECT 
    u.user_id,
    u.current_assets,
    u.current_domains,
    u.current_active_scans,
    u.current_subdomains,
    u.scans_today,
    u.scans_this_month,
    -- Use COALESCE with defaults for missing quota records
    COALESCE(q.max_assets, 3) AS max_assets,
    COALESCE(q.max_domains_per_asset, 10) AS max_domains_per_asset,
    COALESCE(q.max_scans_per_day, 5) AS max_scans_per_day,
    COALESCE(q.max_scans_per_month, 50) AS max_scans_per_month,
    COALESCE(q.max_concurrent_scans, 1) AS max_concurrent_scans,
    COALESCE(q.max_subdomains_stored, 10000) AS max_subdomains_stored,
    -- Limit calculations with COALESCE
    (u.current_assets >= COALESCE(q.max_assets, 3)) AS asset_limit_reached,
    (u.scans_today >= COALESCE(q.max_scans_per_day, 5)) AS daily_limit_reached,
    (u.scans_this_month >= COALESCE(q.max_scans_per_month, 50)) AS monthly_limit_reached,
    (u.current_active_scans >= COALESCE(q.max_concurrent_scans, 1)) AS concurrent_limit_reached,
    (u.current_subdomains >= COALESCE(q.max_subdomains_stored, 10000)) AS storage_limit_reached,
    COALESCE(q.plan_type, 'free') AS plan_type,
    q.plan_expires_at,
    u.updated_at AS usage_updated_at,
    q.updated_at AS quota_updated_at
FROM public.user_usage u
LEFT JOIN public.user_quotas q ON u.user_id = q.user_id;

ALTER VIEW public.user_usage_overview OWNER TO postgres;

COMMENT ON VIEW public.user_usage_overview IS 
'User usage overview with LEFT JOIN to handle missing quota records. Uses free tier defaults when quota record is missing.';

-- Grant permissions on view
GRANT SELECT ON public.user_usage_overview TO anon;
GRANT SELECT ON public.user_usage_overview TO authenticated;
GRANT SELECT ON public.user_usage_overview TO service_role;


-- ============================================================================
-- STEP 3: Add indexes for apex_domain_overview performance
-- ============================================================================

-- Index for apex_domains domain lookups
CREATE INDEX IF NOT EXISTS idx_apex_domains_asset_domain 
ON public.apex_domains(asset_id, domain);

-- Index for faster subdomain source_module lookups  
CREATE INDEX IF NOT EXISTS idx_subdomains_asset_source
ON public.subdomains(asset_id, source_module);


-- ============================================================================
-- STEP 4: Add reset_daily_scans function for scheduled cleanup
-- Should be called at midnight by pg_cron or application scheduler
-- ============================================================================

CREATE OR REPLACE FUNCTION public.reset_daily_scans()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    reset_count INTEGER;
BEGIN
    UPDATE public.user_usage
    SET scans_today = 0,
        scan_date_last_reset = CURRENT_DATE,
        updated_at = NOW()
    WHERE scan_date_last_reset < CURRENT_DATE;
    
    GET DIAGNOSTICS reset_count = ROW_COUNT;
    
    RAISE NOTICE 'Reset daily scan count for % users', reset_count;
    RETURN reset_count;
END;
$$;

ALTER FUNCTION public.reset_daily_scans() OWNER TO postgres;

COMMENT ON FUNCTION public.reset_daily_scans() IS 
'Resets scans_today counter for all users. Call daily at midnight via pg_cron or application scheduler.';

GRANT EXECUTE ON FUNCTION public.reset_daily_scans() TO service_role;


-- ============================================================================
-- STEP 5: Add reset_monthly_scans function for scheduled cleanup
-- Should be called on 1st of each month
-- ============================================================================

CREATE OR REPLACE FUNCTION public.reset_monthly_scans()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    reset_count INTEGER;
    current_month DATE := DATE_TRUNC('month', CURRENT_DATE);
BEGIN
    UPDATE public.user_usage
    SET scans_this_month = 0,
        scan_month_last_reset = current_month,
        updated_at = NOW()
    WHERE scan_month_last_reset < current_month;
    
    GET DIAGNOSTICS reset_count = ROW_COUNT;
    
    RAISE NOTICE 'Reset monthly scan count for % users', reset_count;
    RETURN reset_count;
END;
$$;

ALTER FUNCTION public.reset_monthly_scans() OWNER TO postgres;

COMMENT ON FUNCTION public.reset_monthly_scans() IS 
'Resets scans_this_month counter for all users. Call on 1st of each month via pg_cron or application scheduler.';

GRANT EXECUTE ON FUNCTION public.reset_monthly_scans() TO service_role;


-- ============================================================================
-- STEP 6: Ensure urls_viewed_count has NOT NULL default
-- Prevents NULL arithmetic errors
-- ============================================================================

ALTER TABLE public.user_usage 
ALTER COLUMN urls_viewed_count SET DEFAULT 0;

UPDATE public.user_usage 
SET urls_viewed_count = 0 
WHERE urls_viewed_count IS NULL;

ALTER TABLE public.user_usage
ALTER COLUMN urls_viewed_count SET NOT NULL;
