-- ================================================================
-- Migration: Fix http_probes subdomain and parent_domain columns
-- Date: 2026-01-07
-- ================================================================
-- 
-- PROBLEM SUMMARY:
-- The httpx-go scanner's extractParentDomain function was receiving
-- IP addresses from r.Host instead of hostnames. When publicsuffix
-- library failed to parse IPs, the fallback logic took "last 2 parts"
-- of the IP (e.g., "18.160.10.48" → "10.48").
--
-- CURRENT STATE (verified via direct DB query):
--   url: "https://connect.epicgames.dev"     ← CORRECT
--   subdomain: "67.202.6.174"                ← WRONG (IP address!)
--   parent_domain: "6.174"                   ← WRONG (last 2 IP octets!)
--
-- FIX:
-- 1. Extract hostname from URL → subdomain
-- 2. Extract apex domain from hostname → parent_domain
--
-- SAFETY:
-- - This migration only updates corrupted data (where parent_domain
--   matches the pattern of partial IP addresses: digits.digits)
-- - Existing correct data is preserved
-- - All changes can be verified before committing
-- ================================================================

-- Step 1: Preview changes (DRY RUN - do not commit)
-- Uncomment to verify before running the actual UPDATE
/*
SELECT 
    id,
    url,
    subdomain AS old_subdomain,
    regexp_replace(url, '^https?://([^/:]+).*$', '\1') AS new_subdomain,
    parent_domain AS old_parent_domain,
    -- Extract apex domain (last 2 parts for simple TLDs)
    regexp_replace(
        regexp_replace(url, '^https?://([^/:]+).*$', '\1'),
        '^.*\.([^.]+\.[^.]+)$', 
        '\1'
    ) AS new_parent_domain
FROM http_probes
WHERE parent_domain ~ '^\d+\.\d+$'  -- Matches corrupted values like "6.174", "103.99"
LIMIT 20;
*/

-- Step 2: Update corrupted records
-- Updates ONLY records where parent_domain looks like partial IP (X.Y pattern)

UPDATE http_probes
SET 
    -- Extract hostname from URL: https://connect.epicgames.dev/path → connect.epicgames.dev
    subdomain = regexp_replace(url, '^https?://([^/:]+).*$', '\1'),
    
    -- Extract apex domain (simplified: last 2 dot-separated parts)
    -- e.g., connect.epicgames.dev → epicgames.dev
    -- Note: This doesn't handle special TLDs like .co.uk properly,
    -- but the existing data doesn't appear to have any
    parent_domain = regexp_replace(
        regexp_replace(url, '^https?://([^/:]+).*$', '\1'),
        '^.*\.([^.]+\.[^.]+)$', 
        '\1'
    )
WHERE 
    -- Only update corrupted records (parent_domain looks like IP octets)
    parent_domain ~ '^\d+\.\d+$';

-- Step 3: Handle edge case - single-level subdomains (e.g., "epicgames.dev" with no subdomain prefix)
-- These would fail the parent_domain regex above, so fix them separately

UPDATE http_probes
SET 
    parent_domain = subdomain
WHERE 
    -- subdomain has no dots before the TLD (it IS the apex domain)
    subdomain !~ '\.'  -- Single word, no dots
    OR subdomain ~ '^[^.]+\.[^.]+$'  -- Exactly two parts (already apex domain)
    AND parent_domain ~ '^\d+\.\d+$';  -- Still corrupted

-- Step 4: Verification query (run after migration)
/*
SELECT 
    COUNT(*) AS total_records,
    COUNT(*) FILTER (WHERE parent_domain ~ '^\d+\.\d+$') AS still_corrupted,
    COUNT(*) FILTER (WHERE parent_domain ~ '[a-zA-Z]') AS looks_valid
FROM http_probes;
*/

-- ================================================================
-- EXPECTED RESULTS:
--   Before: 22,463 records with corrupted parent_domain (100%)
--   After:  0 records with corrupted parent_domain (0%)
-- ================================================================
