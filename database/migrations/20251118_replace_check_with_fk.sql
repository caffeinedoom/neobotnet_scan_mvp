-- ================================================================
-- Migration: Replace CHECK constraint with Foreign Key
-- Date: 2025-11-18
-- Issue: 7-layer issue Phase 2 - Auto-validation via FK
-- Author: Neobotnet Development Team
-- ================================================================
--
-- PROBLEM:
-- Layer 2 (batch_scan_jobs) uses a CHECK constraint that must be
-- manually updated whenever a new module is added. This is error-prone
-- (we forgot to add httpx initially).
--
-- SOLUTION:
-- Replace CHECK constraint with a FOREIGN KEY to scan_module_profiles.
-- This provides:
-- - Automatic validation (new modules work immediately after INSERT)
-- - Database-enforced consistency
-- - Zero manual updates needed
--
-- NOTE: 
-- asset_scan_jobs.modules is TEXT[] (array) and cannot use a simple FK.
-- We'll keep its CHECK constraint for now (Phase 3 will address this).
--
-- RISK: LOW - FK is more restrictive than CHECK, but safer
-- ROLLBACK: See rollback section at bottom of file
-- ================================================================

BEGIN;

-- ================================================================
-- Layer 2: batch_scan_jobs (CAN use FK - single TEXT value)
-- ================================================================

-- Drop existing CHECK constraint
ALTER TABLE batch_scan_jobs
DROP CONSTRAINT IF EXISTS valid_module;

-- Add FOREIGN KEY constraint
-- This automatically validates module names against scan_module_profiles
ALTER TABLE batch_scan_jobs
ADD CONSTRAINT fk_module_name 
    FOREIGN KEY (module) 
    REFERENCES scan_module_profiles(module_name)
    ON DELETE RESTRICT;  -- Prevent deleting modules with active scans

-- Add documentation comment
COMMENT ON CONSTRAINT fk_module_name ON batch_scan_jobs IS 
'Foreign key to scan_module_profiles.module_name.
Auto-validates module names against active modules in database.
New modules are automatically allowed when added to scan_module_profiles.
ON DELETE RESTRICT prevents deleting modules that are referenced.';

-- ================================================================
-- Layer 1: asset_scan_jobs (CANNOT use FK - array type)
-- ================================================================
-- Keep CHECK constraint for now, but document it's temporary

ALTER TABLE asset_scan_jobs
DROP CONSTRAINT IF EXISTS valid_modules;

-- Re-add CHECK constraint with better documentation
ALTER TABLE asset_scan_jobs
ADD CONSTRAINT valid_modules 
    CHECK (modules <@ ARRAY['subfinder'::text, 'dnsx'::text, 'httpx'::text]);

COMMENT ON CONSTRAINT valid_modules ON asset_scan_jobs IS 
'TEMPORARY CHECK constraint (Phase 2).
TODO Phase 3: Replace with application-level validation against scan_module_profiles.
PostgreSQL does not support FK constraints on array elements.
MANUAL ACTION REQUIRED: Update this constraint when adding new modules.';

COMMIT;

-- ================================================================
-- Verification Queries
-- ================================================================

-- 1. Verify FK constraint on batch_scan_jobs
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
LEFT JOIN information_schema.constraint_column_usage ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.table_name = 'batch_scan_jobs'
  AND tc.constraint_name = 'fk_module_name'
  AND tc.table_schema = 'public';

-- Expected output:
-- constraint_name | constraint_type | column_name | foreign_table_name      | foreign_column_name
-- ----------------|-----------------|-------------|-------------------------|--------------------
-- fk_module_name  | FOREIGN KEY     | module      | scan_module_profiles    | module_name

-- 2. Verify CHECK constraint still exists on asset_scan_jobs
SELECT 
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(c.oid) AS constraint_definition
FROM pg_constraint c
JOIN pg_class t ON c.conrelid = t.oid
WHERE t.relname = 'asset_scan_jobs'
  AND conname = 'valid_modules';

-- Expected output:
-- constraint_name | constraint_type | constraint_definition
-- ----------------|-----------------|----------------------
-- valid_modules   | c               | CHECK ((modules <@ ARRAY['subfinder'::text, 'dnsx'::text, 'httpx'::text]))

-- ================================================================
-- Test Queries (Optional - DO NOT RUN IN PRODUCTION)
-- ================================================================

-- Test 1: This should succeed (valid module)
-- INSERT INTO batch_scan_jobs (user_id, module, batch_type)
-- VALUES ('00000000-0000-0000-0000-000000000001', 'httpx', 'single_asset');

-- Test 2: This should FAIL (invalid module)
-- INSERT INTO batch_scan_jobs (user_id, module, batch_type)
-- VALUES ('00000000-0000-0000-0000-000000000001', 'invalid_module', 'single_asset');
-- Expected error: violates foreign key constraint "fk_module_name"

-- Cleanup:
-- DELETE FROM batch_scan_jobs WHERE user_id = '00000000-0000-0000-0000-000000000001';

-- ================================================================
-- Rollback Instructions
-- ================================================================
-- Revert to CHECK constraint:
-- 
-- BEGIN;
-- 
-- -- Drop FK
-- ALTER TABLE batch_scan_jobs
-- DROP CONSTRAINT IF EXISTS fk_module_name;
-- 
-- -- Restore CHECK constraint
-- ALTER TABLE batch_scan_jobs
-- ADD CONSTRAINT valid_module 
--     CHECK (module = ANY (ARRAY['subfinder'::text, 'dnsx'::text, 'httpx'::text]));
-- 
-- COMMIT;
-- ================================================================
