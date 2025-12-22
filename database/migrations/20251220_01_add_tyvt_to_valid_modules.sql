-- ============================================================
-- Migration: Add 'tyvt' to valid_modules constraint
-- Module: TYVT (VirusTotal Domain Scanner)
-- Date: 2025-12-20
-- ============================================================
-- Description:
--   Adds 'tyvt' to the valid_modules CHECK constraint on asset_scan_jobs.
--   This allows users to include tyvt in their scan module selections.
-- ============================================================

-- Step 1: Drop the existing constraint
ALTER TABLE asset_scan_jobs
DROP CONSTRAINT IF EXISTS valid_modules;

-- Step 2: Add the updated constraint with 'tyvt' included
ALTER TABLE asset_scan_jobs
ADD CONSTRAINT valid_modules CHECK (
    modules <@ ARRAY['subfinder', 'dnsx', 'httpx', 'katana', 'url-resolver', 'tyvt']::text[]
);

-- Step 3: Add a comment explaining the constraint
COMMENT ON CONSTRAINT valid_modules ON asset_scan_jobs IS 
'Validates that all requested modules are in the allowed list. Updated 2025-12-20 to include tyvt (VirusTotal Domain Scanner).';

-- ============================================================
-- Verification Query (run after migration)
-- ============================================================
-- SELECT conname, pg_get_constraintdef(oid) 
-- FROM pg_constraint 
-- WHERE conrelid = 'asset_scan_jobs'::regclass 
--   AND conname = 'valid_modules';
--
-- Expected output:
-- valid_modules | CHECK ((modules <@ ARRAY['subfinder'::text, 'dnsx'::text, 'httpx'::text, 'katana'::text, 'url-resolver'::text, 'tyvt'::text]))



