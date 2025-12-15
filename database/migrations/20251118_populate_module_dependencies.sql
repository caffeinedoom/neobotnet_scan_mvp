-- ================================================================
-- Data Migration: Populate module dependencies
-- Date: 2025-11-18
-- Issue: 7-layer issue Phase 2 - Migrate from Python to database
-- Author: Neobotnet Development Team
-- ================================================================
--
-- PREREQUISITE:
-- Run 20251118_add_dependencies_to_module_profiles.sql first!
--
-- PURPOSE:
-- Migrate existing module dependencies from Python code to database.
--
-- Current Python DEPENDENCIES dict (scan_pipeline.py line 76):
--   DEPENDENCIES = {
--       "subfinder": [],              # No dependencies
--       "dnsx": ["subfinder"],        # Requires subdomains from subfinder
--       "httpx": ["subfinder"],       # Requires subfinder's stream output
--       "nuclei": ["httpx"],          # Future: requires HTTP probing
--   }
--
-- RISK: LOW - Only updates existing rows, easily reversible
-- ================================================================

BEGIN;

-- Subfinder: No dependencies (produces subdomains from scratch)
UPDATE scan_module_profiles 
SET dependencies = '{}'::TEXT[]
WHERE module_name = 'subfinder';

-- DNSx: Depends on subfinder (needs subdomains to resolve DNS)
UPDATE scan_module_profiles 
SET dependencies = '{subfinder}'::TEXT[]
WHERE module_name = 'dnsx';

-- HTTPx: Depends on subfinder (needs subdomains for HTTP probing)
-- Note: DNSx is auto-included by orchestrator, not a declared dependency
UPDATE scan_module_profiles 
SET dependencies = '{subfinder}'::TEXT[]
WHERE module_name = 'httpx';

COMMIT;

-- ================================================================
-- Verification Queries
-- ================================================================

-- Verify dependencies were set correctly
SELECT 
    module_name,
    dependencies,
    container_name,
    is_active
FROM scan_module_profiles 
WHERE is_active = true
ORDER BY module_name;

-- Expected output:
-- module_name | dependencies   | container_name | is_active
-- ------------|----------------|----------------|----------
-- dnsx        | {subfinder}    | dnsx-scanner   | t
-- httpx       | {subfinder}    | httpx-scanner  | t
-- subfinder   | {}             | subfinder      | t

-- ================================================================
-- Business Logic Note
-- ================================================================
-- DNSx Auto-Inclusion:
-- The orchestrator automatically includes DNSx when subfinder runs,
-- even though it's not in subfinder's dependencies. This is by design
-- because:
-- 1. DNSx provides DNS resolution data needed for persistence
-- 2. It runs in parallel with other modules consuming subfinder's stream
-- 3. It's an implicit architectural requirement, not a dependency
--
-- Therefore, httpx only declares dependency on subfinder, and the
-- orchestrator handles DNSx inclusion automatically.
-- ================================================================

-- ================================================================
-- Rollback Instructions
-- ================================================================
-- Reset to default empty arrays:
-- 
-- BEGIN;
-- UPDATE scan_module_profiles SET dependencies = '{}';
-- COMMIT;
-- ================================================================
