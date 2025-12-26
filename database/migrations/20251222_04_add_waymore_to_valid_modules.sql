-- Migration: Add waymore to valid_modules constraint
-- Date: 2025-12-22
-- Description: Updates asset_scan_jobs.valid_modules constraint to include waymore module
--
-- ISSUE: The valid_modules constraint on asset_scan_jobs does not include 'waymore'
-- This prevents creating asset scan jobs that include waymore as a module.

-- ============================================================================
-- FIX: Update valid_modules constraint on asset_scan_jobs
-- ============================================================================

-- Drop the old constraint
ALTER TABLE asset_scan_jobs DROP CONSTRAINT IF EXISTS valid_modules;

-- Add the new constraint with waymore included
ALTER TABLE asset_scan_jobs ADD CONSTRAINT valid_modules 
    CHECK (modules <@ ARRAY['subfinder'::text, 'dnsx'::text, 'httpx'::text, 'katana'::text, 'url-resolver'::text, 'tyvt'::text, 'waymore'::text]);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    -- Verify the constraint was updated
    IF EXISTS (
        SELECT 1 FROM information_schema.check_constraints 
        WHERE constraint_name = 'valid_modules' 
        AND check_clause LIKE '%waymore%'
    ) THEN
        RAISE NOTICE 'SUCCESS: valid_modules constraint updated to include waymore';
    ELSE
        RAISE WARNING 'Constraint may not include waymore - please verify manually';
    END IF;
END $$;

-- ============================================================================
-- COMMENT
-- ============================================================================

COMMENT ON CONSTRAINT valid_modules ON asset_scan_jobs IS 
    'Validates that all requested modules are in the allowed list. Updated 2025-12-22 to include waymore (Historical URL Discovery).';

