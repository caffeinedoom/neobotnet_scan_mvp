-- ============================================================
-- Migration: Add crawled_endpoints table for Katana module
-- Date: 2024-11-24
-- Author: NeoBot-Net v2 Team
-- Module: katana-go
-- 
-- Purpose: Store web endpoints discovered by Katana web crawler
-- 
-- Key Features:
--   - Global deduplication per asset (url_hash + asset_id unique)
--   - Source URL tracking (which page linked to this endpoint)
--   - Seed URL flagging (distinguish crawl targets from discoveries)
--   - Rediscovery tracking (times_discovered counter)
--   - Status code and content-type metadata
--   - Row-Level Security for multi-tenant isolation
-- 
-- Dependencies:
--   - Requires 'assets' table (for foreign key)
--   - Requires 'batch_scan_jobs' table (for foreign key)
-- 
-- Usage:
--   1. Copy this entire script
--   2. Paste into Supabase SQL Editor
--   3. Execute (runs in transaction - safe to retry)
--   4. Verify with test queries at bottom of file
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: Prerequisite Validation
-- ============================================================
-- Ensure required tables exist before creating foreign keys

DO $$ 
BEGIN
    -- Check if 'assets' table exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'assets'
    ) THEN
        RAISE EXCEPTION 'Required table "assets" does not exist. Cannot create foreign key constraint.';
    END IF;
    
    -- Check if 'batch_scan_jobs' table exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'batch_scan_jobs'
    ) THEN
        RAISE EXCEPTION 'Required table "batch_scan_jobs" does not exist. Cannot create foreign key constraint.';
    END IF;
    
    -- Prerequisite validation passed
END $$;

-- ============================================================
-- SECTION 2: Table Creation
-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."crawled_endpoints" (
    -- Primary Key
    "id" UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    
    -- Foreign Keys (Links to assets and scan jobs)
    "asset_id" UUID NOT NULL,
    "scan_job_id" UUID,
    
    -- URL Information
    "url" TEXT NOT NULL,
    "url_hash" TEXT NOT NULL,  -- SHA256 hash of normalized URL (64 chars)
    "method" TEXT DEFAULT 'GET' NOT NULL,
    
    -- Discovery Tracking
    "source_url" TEXT,  -- The page that linked to this endpoint (FIRST discoverer)
    "is_seed_url" BOOLEAN DEFAULT false NOT NULL,  -- True if this was an initial crawl target from HTTPx
    
    -- HTTP Response Metadata
    "status_code" INTEGER,
    "content_type" TEXT,
    "content_length" BIGINT,
    
    -- Temporal Tracking (for rediscovery analysis)
    "first_seen_at" TIMESTAMPTZ NOT NULL,
    "last_seen_at" TIMESTAMPTZ NOT NULL,
    "times_discovered" INTEGER DEFAULT 1 NOT NULL,
    
    -- Audit Timestamp
    "created_at" TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================
-- SECTION 3: Constraints
-- ============================================================

-- HTTP Method Constraint (ensure valid HTTP verbs only)
ALTER TABLE "public"."crawled_endpoints"
ADD CONSTRAINT "crawled_endpoints_method_check" 
CHECK ("method" = ANY (ARRAY['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']));

-- Times Discovered Constraint (must be >= 1)
ALTER TABLE "public"."crawled_endpoints"
ADD CONSTRAINT "crawled_endpoints_times_discovered_check" 
CHECK ("times_discovered" >= 1);

-- Unique Constraint (global deduplication per asset)
-- Note: This prevents duplicate endpoints within the same asset
-- Same URL in different assets = separate records (intentional)
ALTER TABLE "public"."crawled_endpoints"
ADD CONSTRAINT "crawled_endpoints_asset_url_unique" 
UNIQUE ("asset_id", "url_hash");

-- Foreign Key: Asset (CASCADE delete - when asset deleted, remove all endpoints)
-- Reasoning: Endpoints are meaningless without parent asset
ALTER TABLE "public"."crawled_endpoints"
ADD CONSTRAINT "crawled_endpoints_asset_id_fkey" 
FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;

-- Foreign Key: Scan Job (SET NULL - scan job is temporary, endpoint is permanent)
-- Reasoning: Endpoint might be rediscovered in future scans, don't cascade delete
ALTER TABLE "public"."crawled_endpoints"
ADD CONSTRAINT "crawled_endpoints_scan_job_id_fkey" 
FOREIGN KEY ("scan_job_id") REFERENCES "public"."batch_scan_jobs"("id") ON DELETE SET NULL;

-- ============================================================
-- SECTION 4: Indexes for Performance
-- ============================================================
-- Index strategy: Optimize for common query patterns
-- Trade-off: Slower inserts, but Katana runs infrequently (acceptable)

-- Index 1: PRIMARY DEDUPLICATION LOOKUP
-- Query: "Does this URL already exist for this asset?"
-- Used by: ON CONFLICT logic during bulk inserts
CREATE UNIQUE INDEX "idx_crawled_endpoints_asset_url_hash" 
ON "public"."crawled_endpoints" USING btree ("asset_id", "url_hash");

-- Index 2: ASSET DASHBOARD
-- Query: "SELECT * FROM crawled_endpoints WHERE asset_id = ?"
-- Used by: Frontend dashboard, API endpoint listing
CREATE INDEX "idx_crawled_endpoints_asset_id" 
ON "public"."crawled_endpoints" USING btree ("asset_id");

-- Index 3: SCAN TRACKING
-- Query: "SELECT * FROM crawled_endpoints WHERE scan_job_id = ?"
-- Used by: Scan result retrieval, "what did this scan discover?"
CREATE INDEX "idx_crawled_endpoints_scan_job_id" 
ON "public"."crawled_endpoints" USING btree ("scan_job_id");

-- Index 4: STATUS CODE FILTERING
-- Query: "SELECT * WHERE status_code = 200" (or 404, 500, etc.)
-- Used by: Dashboard filters, vulnerability analysis
CREATE INDEX "idx_crawled_endpoints_status_code" 
ON "public"."crawled_endpoints" USING btree ("status_code");

-- Index 5: SEED URL FILTERING
-- Query: "SELECT * WHERE is_seed_url = false" (hide seed URLs)
-- Used by: Dashboard toggle "Hide seed URLs"
CREATE INDEX "idx_crawled_endpoints_is_seed_url" 
ON "public"."crawled_endpoints" USING btree ("is_seed_url");

-- Index 6: URL HASH LOOKUP
-- Query: "SELECT * WHERE url_hash = ?" (exact match)
-- Used by: Deduplication checks, exact URL lookups
CREATE INDEX "idx_crawled_endpoints_url_hash" 
ON "public"."crawled_endpoints" USING btree ("url_hash");

-- Index 7: TIMELINE ANALYSIS
-- Query: "SELECT * ORDER BY first_seen_at DESC LIMIT 100" (newest first)
-- Used by: Discovery timeline, "what's new?" dashboard widget
CREATE INDEX "idx_crawled_endpoints_first_seen" 
ON "public"."crawled_endpoints" USING btree ("first_seen_at" DESC);

-- ============================================================
-- SECTION 5: Row-Level Security (RLS)
-- ============================================================
-- Multi-tenant isolation: Users can only see endpoints for their own assets

-- Enable RLS on table
ALTER TABLE "public"."crawled_endpoints" ENABLE ROW LEVEL SECURITY;

-- Policy 1: SELECT (Read-only access to own endpoints)
-- Reasoning: Users should view their scan results but not modify them
-- Service role bypasses this (used by Katana container for inserts)
CREATE POLICY "Users can view their own crawled endpoints"
ON "public"."crawled_endpoints"
FOR SELECT
USING (
    EXISTS (
        SELECT 1 
        FROM "public"."assets"
        WHERE "assets"."id" = "crawled_endpoints"."asset_id"
        AND "assets"."user_id" = "auth"."uid"()
    )
);

-- Note: No INSERT/UPDATE/DELETE policies for users
-- Only service role (backend/containers) can modify data
-- Users delete endpoints by deleting parent asset (CASCADE)

-- ============================================================
-- SECTION 6: Documentation (Comments)
-- ============================================================
-- Add descriptions for table and columns (visible in Supabase dashboard)

COMMENT ON TABLE "public"."crawled_endpoints" IS 
'Stores web endpoints discovered by Katana web crawler. Includes URL metadata, status codes, source tracking, and deduplication fields. Used for attack surface mapping and site structure analysis.';

-- Column Comments
COMMENT ON COLUMN "public"."crawled_endpoints"."url" IS 
'Full URL of the discovered endpoint (normalized for deduplication). Example: https://example.com/api/users?id=123';

COMMENT ON COLUMN "public"."crawled_endpoints"."url_hash" IS 
'SHA256 hash of normalized URL for fast lookups and deduplication. 64-character hex string. Generated by Go code using crypto/sha256.';

COMMENT ON COLUMN "public"."crawled_endpoints"."method" IS 
'HTTP method for this endpoint. Defaults to GET (most common). POST indicates form submission or API endpoint.';

COMMENT ON COLUMN "public"."crawled_endpoints"."source_url" IS 
'The URL from which this endpoint was discovered (the page that linked here). Used for attack surface mapping and site structure analysis. Stores FIRST discoverer only (see times_discovered for rediscovery count).';

COMMENT ON COLUMN "public"."crawled_endpoints"."is_seed_url" IS 
'True if this URL was used as an initial seed for crawling (from http_probes table). Use for UI filtering to distinguish crawl targets from discovered links. Seed URLs typically have higher confidence/importance.';

COMMENT ON COLUMN "public"."crawled_endpoints"."status_code" IS 
'HTTP response status code when endpoint was probed. NULL if endpoint discovered but not yet probed (e.g., from JavaScript or sitemap). Common values: 200 (OK), 404 (Not Found), 403 (Forbidden), 500 (Server Error).';

COMMENT ON COLUMN "public"."crawled_endpoints"."content_type" IS 
'HTTP Content-Type header value. Examples: "text/html", "application/json", "image/png". Used for filtering (exclude images/CSS) and identifying API endpoints.';

COMMENT ON COLUMN "public"."crawled_endpoints"."content_length" IS 
'HTTP Content-Length header value (bytes). NULL if not provided. Used for identifying large responses or empty pages.';

COMMENT ON COLUMN "public"."crawled_endpoints"."times_discovered" IS 
'Number of times this URL was discovered across crawls. Higher values indicate hub pages or frequently linked resources (navigation menus, sitemaps, popular pages). Incremented via ON CONFLICT logic.';

COMMENT ON COLUMN "public"."crawled_endpoints"."first_seen_at" IS 
'Timestamp when this URL was first discovered. Immutable after initial insert. Used for timeline analysis and tracking when endpoints appeared.';

COMMENT ON COLUMN "public"."crawled_endpoints"."last_seen_at" IS 
'Timestamp when this URL was most recently rediscovered. Updated via ON CONFLICT logic. Used for staleness detection (endpoints not seen in recent scans might be removed).';

-- ============================================================
-- SECTION 7: Ownership
-- ============================================================
-- Set table owner to postgres (standard for Supabase)

ALTER TABLE "public"."crawled_endpoints" OWNER TO "postgres";

-- ============================================================
-- SECTION 8: Migration Complete
-- ============================================================

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES (Run these after migration succeeds)
-- ============================================================
-- Copy these into Supabase SQL Editor separately to verify schema

/*

-- 1. Verify table exists
SELECT EXISTS (
    SELECT 1 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'crawled_endpoints'
) AS table_exists;
-- Expected: true

-- 2. Verify columns
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'crawled_endpoints'
ORDER BY ordinal_position;
-- Expected: 14 columns

-- 3. Verify indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'crawled_endpoints'
AND schemaname = 'public'
ORDER BY indexname;
-- Expected: 8 indexes (1 primary key + 7 performance indexes)

-- 4. Verify constraints
SELECT conname, contype, pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conrelid = 'public.crawled_endpoints'::regclass
ORDER BY conname;
-- Expected: 5 constraints (2 CHECK, 1 UNIQUE, 2 FOREIGN KEY)

-- 5. Verify RLS policies
SELECT polname, polcmd, qual, with_check
FROM pg_policy
WHERE polrelid = 'public.crawled_endpoints'::regclass;
-- Expected: 1 policy (SELECT only)

-- 6. Test insert (should succeed with service role key)
INSERT INTO crawled_endpoints (
    asset_id,
    url,
    url_hash,
    method,
    source_url,
    is_seed_url,
    status_code,
    content_type,
    first_seen_at,
    last_seen_at,
    times_discovered
) VALUES (
    (SELECT id FROM assets LIMIT 1),  -- Replace with valid asset_id
    'https://example.com/test',
    'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',  -- SHA256 of 'test'
    'GET',
    'https://example.com',
    false,
    200,
    'text/html',
    NOW(),
    NOW(),
    1
);
-- Expected: 1 row inserted

-- 7. Test deduplication (should update times_discovered)
INSERT INTO crawled_endpoints (
    asset_id,
    url,
    url_hash,
    method,
    source_url,
    is_seed_url,
    status_code,
    first_seen_at,
    last_seen_at,
    times_discovered
) VALUES (
    (SELECT id FROM assets LIMIT 1),
    'https://example.com/test',
    'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',
    'GET',
    'https://example.com/other',
    false,
    200,
    NOW(),
    NOW(),
    1
)
ON CONFLICT (asset_id, url_hash) DO UPDATE SET
    last_seen_at = EXCLUDED.last_seen_at,
    times_discovered = crawled_endpoints.times_discovered + 1,
    status_code = COALESCE(EXCLUDED.status_code, crawled_endpoints.status_code);
-- Expected: times_discovered incremented to 2

-- 8. Verify deduplication worked
SELECT url, times_discovered, first_seen_at, last_seen_at
FROM crawled_endpoints
WHERE url_hash = 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3';
-- Expected: 1 row, times_discovered = 2

-- 9. Cleanup test data
DELETE FROM crawled_endpoints 
WHERE url_hash = 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3';

*/

-- ============================================================
-- END OF MIGRATION
-- ============================================================
-- Status: Ready for deployment
-- Next Steps:
--   1. Test on local/VPS Supabase instance first
--   2. Verify with queries above
--   3. Deploy to production Supabase
--   4. Mark Phase 1.4 complete in PROGRESS_TRACKER.md
-- ============================================================

