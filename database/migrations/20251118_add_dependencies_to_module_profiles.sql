-- ================================================================
-- Migration: Add dependencies column to scan_module_profiles
-- Date: 2025-11-18
-- Issue: 7-layer issue Phase 2 - Database-driven module config
-- Author: Neobotnet Development Team
-- ================================================================
--
-- PROBLEM:
-- Module dependencies are currently hardcoded in Python (Layer 4):
--   DEPENDENCIES = {
--       "subfinder": [],
--       "dnsx": ["subfinder"],
--       "httpx": ["subfinder"],
--   }
--
-- This requires code changes for every new module, violating DRY
-- principle and making the system less flexible.
--
-- SOLUTION:
-- Add dependencies column to scan_module_profiles table to store
-- module dependencies in the database. This allows:
-- - Dynamic loading at runtime
-- - No code changes when adding modules
-- - Single source of truth for all module config
--
-- RISK: LOW - Adding new column with default value, no data loss
-- ROLLBACK: See rollback section at bottom of file
-- ================================================================

BEGIN;

-- Add dependencies column
ALTER TABLE scan_module_profiles
ADD COLUMN IF NOT EXISTS dependencies TEXT[] DEFAULT '{}' NOT NULL;

-- Add documentation comment
COMMENT ON COLUMN scan_module_profiles.dependencies IS 
'Array of module names that must execute before this module.
Example: httpx depends on [subfinder] because it needs subdomain data.
Empty array means no dependencies.
Used by backend to resolve execution order automatically.';

COMMIT;

-- ================================================================
-- Verification Query
-- ================================================================

-- Verify column was added
SELECT 
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'scan_module_profiles'
  AND column_name = 'dependencies';

-- Expected output:
-- column_name  | data_type | column_default | is_nullable
-- -------------|-----------|----------------|-------------
-- dependencies | ARRAY     | '{}'::text[]   | NO

-- ================================================================
-- Rollback Instructions
-- ================================================================
-- If needed, remove the column:
-- 
-- BEGIN;
-- ALTER TABLE scan_module_profiles
-- DROP COLUMN IF EXISTS dependencies;
-- COMMIT;
-- ================================================================
