-- Migration: LEAN Public Read Access
-- Date: 2025-12-15
-- Purpose: Enable public read access for all authenticated users (LEAN model)
-- 
-- In the LEAN model:
-- - All authenticated users can READ all reconnaissance data
-- - Write operations remain restricted to service role (CLI operator)
-- - This enables the public data sharing model for bug bounty researchers

-- ============================================================================
-- ASSETS TABLE - Public Read Access
-- ============================================================================

-- Drop existing user-specific policy if exists
DROP POLICY IF EXISTS "Users can view own assets" ON "public"."assets";
DROP POLICY IF EXISTS "Users can insert own assets" ON "public"."assets";
DROP POLICY IF EXISTS "Users can update own assets" ON "public"."assets";
DROP POLICY IF EXISTS "Users can delete own assets" ON "public"."assets";

-- Create new public read policy for authenticated users
CREATE POLICY "Authenticated users can read all assets" 
    ON "public"."assets" 
    FOR SELECT 
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- Service role can manage assets (for CLI operator)
CREATE POLICY "Service role can manage assets" 
    ON "public"."assets" 
    FOR ALL 
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- APEX_DOMAINS TABLE - Public Read Access
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own domains" ON "public"."apex_domains";
DROP POLICY IF EXISTS "Users can insert own domains" ON "public"."apex_domains";
DROP POLICY IF EXISTS "Users can update own domains" ON "public"."apex_domains";
DROP POLICY IF EXISTS "Users can delete own domains" ON "public"."apex_domains";

CREATE POLICY "Authenticated users can read all domains" 
    ON "public"."apex_domains" 
    FOR SELECT 
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "Service role can manage domains" 
    ON "public"."apex_domains" 
    FOR ALL 
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- SUBDOMAINS TABLE - Public Read Access
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own subdomains" ON "public"."subdomains";
DROP POLICY IF EXISTS "Users can insert subdomains" ON "public"."subdomains";

CREATE POLICY "Authenticated users can read all subdomains" 
    ON "public"."subdomains" 
    FOR SELECT 
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "Service role can manage subdomains" 
    ON "public"."subdomains" 
    FOR ALL 
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- DNS_RECORDS TABLE - Public Read Access
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own DNS records" ON "public"."dns_records";
DROP POLICY IF EXISTS "Users can insert DNS records" ON "public"."dns_records";

CREATE POLICY "Authenticated users can read all DNS records" 
    ON "public"."dns_records" 
    FOR SELECT 
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "Service role can manage DNS records" 
    ON "public"."dns_records" 
    FOR ALL 
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- HTTP_PROBES TABLE - Public Read Access
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own HTTP probes" ON "public"."http_probes";
DROP POLICY IF EXISTS "Users can insert HTTP probes" ON "public"."http_probes";

CREATE POLICY "Authenticated users can read all HTTP probes" 
    ON "public"."http_probes" 
    FOR SELECT 
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "Service role can manage HTTP probes" 
    ON "public"."http_probes" 
    FOR ALL 
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- ASSET_SCAN_JOBS TABLE - Public Read Access
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own scan jobs" ON "public"."asset_scan_jobs";
DROP POLICY IF EXISTS "Users can insert scan jobs" ON "public"."asset_scan_jobs";
DROP POLICY IF EXISTS "Users can update own scan jobs" ON "public"."asset_scan_jobs";

CREATE POLICY "Authenticated users can read all scan jobs" 
    ON "public"."asset_scan_jobs" 
    FOR SELECT 
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "Service role can manage scan jobs" 
    ON "public"."asset_scan_jobs" 
    FOR ALL 
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- BATCH_SCAN_JOBS TABLE - Public Read Access
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own batch scans" ON "public"."batch_scan_jobs";
DROP POLICY IF EXISTS "Users can insert batch scans" ON "public"."batch_scan_jobs";
DROP POLICY IF EXISTS "Users can update own batch scans" ON "public"."batch_scan_jobs";

CREATE POLICY "Authenticated users can read all batch scans" 
    ON "public"."batch_scan_jobs" 
    FOR SELECT 
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "Service role can manage batch scans" 
    ON "public"."batch_scan_jobs" 
    FOR ALL 
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- SCAN_MODULE_PROFILES TABLE - Public Read Access (already public)
-- ============================================================================

DROP POLICY IF EXISTS "Anyone can read module profiles" ON "public"."scan_module_profiles";

CREATE POLICY "Authenticated users can read module profiles" 
    ON "public"."scan_module_profiles" 
    FOR SELECT 
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

CREATE POLICY "Service role can manage module profiles" 
    ON "public"."scan_module_profiles" 
    FOR ALL 
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- API_KEYS TABLE - Keep user-specific (users manage own keys)
-- ============================================================================
-- No changes needed - API keys remain user-specific


-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify policies were created
SELECT 
    schemaname, 
    tablename, 
    policyname, 
    cmd, 
    roles
FROM pg_policies 
WHERE schemaname = 'public' 
  AND policyname LIKE '%Authenticated users can read%'
ORDER BY tablename;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON POLICY "Authenticated users can read all assets" ON "public"."assets" IS 
    'LEAN model: All authenticated users can read all reconnaissance data. Part of public data sharing for bug bounty researchers.';

COMMENT ON POLICY "Authenticated users can read all subdomains" ON "public"."subdomains" IS 
    'LEAN model: All authenticated users can read all reconnaissance data. Part of public data sharing for bug bounty researchers.';

COMMENT ON POLICY "Authenticated users can read all DNS records" ON "public"."dns_records" IS 
    'LEAN model: All authenticated users can read all reconnaissance data. Part of public data sharing for bug bounty researchers.';

COMMENT ON POLICY "Authenticated users can read all HTTP probes" ON "public"."http_probes" IS 
    'LEAN model: All authenticated users can read all reconnaissance data. Part of public data sharing for bug bounty researchers.';

