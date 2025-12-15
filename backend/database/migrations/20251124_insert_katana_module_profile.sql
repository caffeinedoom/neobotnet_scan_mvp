-- ============================================================
-- Migration: Insert Katana module profile
-- Date: 2024-11-24
-- Author: NeoBot-Net v2 Team
-- Module: katana-go
-- Phase: Phase 2 - Module Profile Configuration
-- 
-- Purpose: Register Katana web crawler module in scan_module_profiles
-- 
-- Module Type: Consumer (depends on HTTPx for seed URLs)
-- Input: http_probes table (status_code = 200)
-- Output: crawled_endpoints table
-- 
-- Key Characteristics:
--   - Headless crawling with JavaScript rendering
--   - Crawl depth: 1 level (configurable)
--   - Scope control via apex domains
--   - Global deduplication per asset
--   - Source URL tracking for attack surface mapping
-- 
-- Prerequisites:
--   - httpx module must be registered (dependency)
--   - crawled_endpoints table must exist (Phase 1)
-- 
-- Usage:
--   1. Verify httpx module exists: SELECT * FROM scan_module_profiles WHERE module_name = 'httpx';
--   2. Copy this entire script
--   3. Paste into Supabase SQL Editor
--   4. Execute (safe to retry - uses INSERT ON CONFLICT)
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: Prerequisite Validation
-- ============================================================

DO $$ 
BEGIN
    -- Verify httpx module exists (required dependency)
    IF NOT EXISTS (
        SELECT 1 
        FROM scan_module_profiles 
        WHERE module_name = 'httpx' 
        AND is_active = true
    ) THEN
        RAISE EXCEPTION 'Required module "httpx" not found or inactive. Katana depends on HTTPx for seed URLs.';
    END IF;
    
    -- Verify crawled_endpoints table exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'crawled_endpoints'
    ) THEN
        RAISE EXCEPTION 'Required table "crawled_endpoints" does not exist. Run Phase 1 migration first.';
    END IF;
END $$;

-- ============================================================
-- SECTION 2: Insert Module Profile
-- ============================================================

INSERT INTO scan_module_profiles (
    module_name,
    version,
    supports_batching,
    max_batch_size,
    resource_scaling,
    estimated_duration_per_domain,
    task_definition_template,
    container_name,
    dependencies,
    optimization_hints,
    is_active
) VALUES (
    -- Module Identity
    'katana',                           -- ① Module name (matches container family)
    '1.0',                              -- ② Version (semantic versioning)
    
    -- Batching Configuration
    true,                               -- ③ Supports batching (process multiple URLs per task)
    20,                                 -- ④ Max batch size (20 URLs per ECS task)
                                        --    Rationale: 20 URLs × 5 min = 100 min < 120 min timeout
                                        --    Headless crawling is slower than simple HTTP requests
    
    -- Resource Scaling Rules
    '{
        "domain_count_ranges": [
            {
                "min_domains": 1,
                "max_domains": 20,
                "cpu": 1024,
                "memory": 2048,
                "description": "Small batch (1-20 URLs) - Headless Chrome with light concurrency"
            },
            {
                "min_domains": 21,
                "max_domains": 50,
                "cpu": 2048,
                "memory": 4096,
                "description": "Medium batch (21-50 URLs) - Parallel crawling with 10 workers"
            },
            {
                "min_domains": 51,
                "max_domains": 100,
                "cpu": 4096,
                "memory": 8192,
                "description": "Large batch (51-100 URLs) - High concurrency, split recommended"
            }
        ],
        "scaling_notes": "Katana uses headless Chrome for JavaScript rendering. Memory requirements are higher than simple HTTP modules. CPU scales with concurrency (10-20 parallel workers). Recommended: Keep batches ≤20 URLs for optimal performance/cost ratio."
    }'::jsonb,
    
    -- Performance Estimates
    20,                                 -- ⑥ Estimated duration per URL (seconds)
                                        --    Breakdown: 15s crawl + 3s dedup + 2s database insert
                                        --    Conservative estimate for headless mode with JS parsing
    
    -- ECS Integration
    'neobotnet-v2-dev-katana',         -- ⑦ ECS task definition family (Fargate)
    'katana-scanner',                   -- ⑧ Container name in task definition
    
    -- Dependency Graph
    ARRAY['httpx'],                     -- ⑨ Depends on HTTPx (needs HTTP probes with 200 OK)
                                        --    Execution order: subfinder → dnsx → httpx → katana
    
    -- Optimization Hints (Module-Specific Configuration)
    '{
        "requires_database_fetch": true,
        "requires_asset_id": true,
        "streams_output": false,
        "crawl_depth": 1,
        "headless_mode": true,
        "javascript_parsing": true,
        "rate_limit": 150,
        "concurrency": 10,
        "parallelism": 10,
        "timeout": 10,
        "strategy": "depth-first",
        "scope_control": "apex_domains",
        "input_filter": "status_code_200",
        "extension_blacklist": ["css", "js", "jpg", "jpeg", "png", "svg", "gif", "mp4", "webm", "mp3", "woff", "woff2", "ttf", "eot", "ico"],
        "seed_url_tracking": true,
        "deduplication_enabled": true,
        "output_table": "crawled_endpoints"
    }'::jsonb,
    
    -- Status
    true                                -- ⑪ Active (module available for use)
)
ON CONFLICT (module_name) DO UPDATE
SET 
    version = EXCLUDED.version,
    supports_batching = EXCLUDED.supports_batching,
    max_batch_size = EXCLUDED.max_batch_size,
    resource_scaling = EXCLUDED.resource_scaling,
    estimated_duration_per_domain = EXCLUDED.estimated_duration_per_domain,
    task_definition_template = EXCLUDED.task_definition_template,
    container_name = EXCLUDED.container_name,
    dependencies = EXCLUDED.dependencies,
    optimization_hints = EXCLUDED.optimization_hints,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

COMMIT;

-- ============================================================
-- SECTION 3: Verification Queries
-- ============================================================

-- Run these queries AFTER migration to verify success

/*

-- 1. Verify Katana module was inserted
SELECT 
    module_name,
    version,
    supports_batching,
    max_batch_size,
    estimated_duration_per_domain,
    container_name,
    dependencies,
    is_active,
    created_at
FROM scan_module_profiles
WHERE module_name = 'katana';

-- Expected output:
-- module_name | version | supports_batching | max_batch_size | estimated_duration_per_domain | container_name  | dependencies | is_active
-- ------------|---------|-------------------|----------------|-------------------------------|-----------------|--------------|----------
-- katana      | 1.0     | t                 | 20             | 20                            | katana-scanner  | {httpx}      | t


-- 2. Verify resource scaling configuration
SELECT 
    module_name,
    jsonb_pretty(resource_scaling) AS resource_config
FROM scan_module_profiles
WHERE module_name = 'katana';

-- Expected: Should show 3 scaling ranges (1-20, 21-50, 51-100)


-- 3. Verify optimization hints
SELECT 
    module_name,
    jsonb_pretty(optimization_hints) AS optimization_config
FROM scan_module_profiles
WHERE module_name = 'katana';

-- Expected: Should show crawl_depth, headless_mode, concurrency, etc.


-- 4. Test resource calculation function
SELECT calculate_module_resources('katana', 15);

-- Expected output (JSONB):
-- {
--   "cpu": 1024,
--   "memory": 2048,
--   "estimated_duration_minutes": 5,
--   "description": "Small batch (1-20 URLs)",
--   "domain_count": 15,
--   "module_name": "katana"
-- }


-- 5. Test batch size optimization
SELECT get_optimal_batch_sizes('katana', 75);

-- Expected output (JSONB):
-- {
--   "total_domains": 75,
--   "batch_sizes": [20, 20, 20, 15],
--   "total_batches": 4,
--   "max_batch_size": 20,
--   "module_name": "katana"
-- }


-- 6. Verify dependency chain
SELECT 
    module_name,
    dependencies,
    container_name
FROM scan_module_profiles
WHERE module_name IN ('subfinder', 'dnsx', 'httpx', 'katana')
ORDER BY 
    CASE module_name
        WHEN 'subfinder' THEN 1
        WHEN 'dnsx' THEN 2
        WHEN 'httpx' THEN 3
        WHEN 'katana' THEN 4
    END;

-- Expected execution order:
-- module_name | dependencies      | container_name
-- ------------|-------------------|------------------
-- subfinder   | {}                | subfinder-scanner
-- dnsx        | {subfinder}       | dnsx-scanner
-- httpx       | {subfinder}       | httpx-scanner
-- katana      | {httpx}           | katana-scanner


-- 7. Verify all modules are active
SELECT 
    module_name,
    is_active,
    version,
    created_at
FROM scan_module_profiles
ORDER BY created_at DESC;

-- Expected: All modules should have is_active = true

*/

-- ============================================================
-- SECTION 4: Module Profile Documentation
-- ============================================================

COMMENT ON COLUMN scan_module_profiles.optimization_hints IS 
'Module-specific configuration flags stored as JSONB.

Common flags:
- requires_database_fetch: Module needs to query database for input data
- requires_asset_id: Module needs asset context for scope control
- streams_output: Module publishes to Redis Streams
- input_filter: Filtering criteria for input data (e.g., "status_code_200")
- output_table: Target table for results

Katana-specific flags:
- crawl_depth: Maximum depth for recursive crawling (default: 1)
- headless_mode: Enable headless Chrome for JS rendering (default: true)
- javascript_parsing: Parse JavaScript for URLs (default: true)
- rate_limit: Max requests per second (default: 150)
- concurrency: Parallel crawling goroutines (default: 10)
- strategy: Crawl strategy (depth-first or breadth-first)
- scope_control: How to enforce scope (apex_domains = use asset apex domains)
- extension_blacklist: File extensions to skip (images, CSS, fonts)
- seed_url_tracking: Track which URLs were initial crawl targets
- deduplication_enabled: Enable in-memory + database deduplication';

-- ============================================================
-- END OF MIGRATION
-- ============================================================

-- Status: Ready for deployment
-- Next Steps:
--   1. Run verification queries above
--   2. Test with calculate_module_resources() function
--   3. Mark Phase 2 complete in PROGRESS_TRACKER.md
--   4. Proceed to Phase 3 (Container Implementation)
-- ============================================================

