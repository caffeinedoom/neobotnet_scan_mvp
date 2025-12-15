-- ================================================================
-- Migration: Add HTTPx to batch_scan_jobs valid_module constraint
-- Date: 2025-11-18
-- Issue: Layer 2 missing httpx module (7-layer issue Phase 1)
-- Author: Neobotnet Development Team
-- ================================================================
-- 
-- PROBLEM:
-- The batch_scan_jobs table has a CHECK constraint that only allows
-- 'subfinder' and 'dnsx' modules, but HTTPx is now implemented and
-- being used in production. This causes constraint violations when
-- trying to use HTTPx with batch scanning.
--
-- SOLUTION:
-- Add 'httpx' to the valid_module CHECK constraint.
--
-- RISK: LOW - Simple constraint modification, no data changes
-- ROLLBACK: See rollback section at bottom of file
-- ================================================================

BEGIN;

-- Drop old constraint (only allows subfinder, dnsx)
ALTER TABLE batch_scan_jobs
DROP CONSTRAINT IF EXISTS valid_module;

-- Add new constraint with httpx included
ALTER TABLE batch_scan_jobs
ADD CONSTRAINT valid_module 
    CHECK (module = ANY (ARRAY['subfinder'::text, 'dnsx'::text, 'httpx'::text]));

-- Add documentation comment
COMMENT ON CONSTRAINT valid_module ON batch_scan_jobs IS 
'Validates module names. Allows: subfinder, dnsx, httpx. 
Updated 2025-11-18 to include httpx (Phase 1 of 7-layer fix).
NOTE: This will be replaced with FK constraint in Phase 2.';

COMMIT;

-- ================================================================
-- Verification Queries
-- ================================================================

-- Verify constraint was updated
SELECT 
    conname AS constraint_name,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conname = 'valid_module'
  AND conrelid = 'batch_scan_jobs'::regclass;

-- Expected output:
-- constraint_name | constraint_definition
-- ----------------|----------------------
-- valid_module    | CHECK ((module = ANY (ARRAY['subfinder'::text, 'dnsx'::text, 'httpx'::text])))

-- ================================================================
-- Test Queries (Optional)
-- ================================================================

-- Test: These should all succeed now
-- INSERT INTO batch_scan_jobs (user_id, module, batch_type) 
-- VALUES 
--     ('00000000-0000-0000-0000-000000000001', 'subfinder', 'single_asset'),
--     ('00000000-0000-0000-0000-000000000001', 'dnsx', 'single_asset'),
--     ('00000000-0000-0000-0000-000000000001', 'httpx', 'single_asset');

-- Cleanup test data:
-- DELETE FROM batch_scan_jobs WHERE user_id = '00000000-0000-0000-0000-000000000001';

-- ================================================================
-- Rollback Instructions
-- ================================================================
-- If needed, revert to original constraint:
-- 
-- BEGIN;
-- ALTER TABLE batch_scan_jobs
-- DROP CONSTRAINT valid_module;
-- ADD CONSTRAINT valid_module 
--     CHECK (module = ANY (ARRAY['subfinder'::text, 'dnsx'::text]));
-- COMMIT;
-- ================================================================
