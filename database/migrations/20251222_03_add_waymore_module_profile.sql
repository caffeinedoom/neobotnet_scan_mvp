-- Migration: Add Waymore module profile
-- Date: 2025-12-22
-- Description: Registers the Waymore module for historical URL discovery from
--              Wayback Machine, Common Crawl, Alien Vault, URLScan, VirusTotal.
--
-- Architecture:
--   Pattern: Producer (parallel with Subfinder)
--   Dependencies: None
--   Downstream Consumer: URL Resolver
--   Output: Streams URLs to Redis, stores to historical_urls table

-- ============================================================================
-- INSERT MODULE PROFILE
-- ============================================================================

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
    'waymore',
    '1.0',
    true,
    50,  -- Conservative batch size due to archive API rate limits
    '{
        "domain_count_ranges": [
            {
                "min_domains": 1,
                "max_domains": 5,
                "cpu": 512,
                "memory": 1024,
                "description": "Light scan (1-5 domains)"
            },
            {
                "min_domains": 6,
                "max_domains": 20,
                "cpu": 1024,
                "memory": 2048,
                "description": "Medium scan (6-20 domains)"
            },
            {
                "min_domains": 21,
                "max_domains": 50,
                "cpu": 2048,
                "memory": 4096,
                "description": "Heavy scan (21-50 domains)"
            }
        ],
        "scaling_notes": "Waymore is I/O bound (archive API calls). Rate limiting from sources is the primary bottleneck, not CPU/memory."
    }'::jsonb,
    600,  -- 10 minutes per domain (archive APIs can be slow)
    'neobotnet-v2-dev-waymore',
    'waymore-scanner',
    ARRAY[]::text[],  -- NO DEPENDENCIES: runs parallel with subfinder
    '{
        "description": "Historical URL discovery from Wayback Machine, Common Crawl, Alien Vault OTX, URLScan, VirusTotal",
        "requires_database_fetch": false,
        "requires_asset_id": true,
        "streams_output": true,
        "output_stream_pattern": "scan:{scan_job_id}:waymore:urls",
        "output_table": "historical_urls",
        "parallel_with": ["subfinder"],
        "downstream_consumer": "url-resolver",
        "providers": ["wayback", "commoncrawl", "alienvault", "urlscan", "virustotal"],
        "default_url_limit": 5000,
        "api_keys_optional": ["URLSCAN_API_KEY", "VIRUSTOTAL_API_KEY", "ALIENVAULT_API_KEY"],
        "rate_limit_notes": "Archive APIs have rate limits. URLScan requires API key for full access. VirusTotal has strict limits on free tier."
    }'::jsonb,
    true
)
ON CONFLICT (module_name) DO UPDATE SET
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

-- ============================================================================
-- ADD TO VALID MODULES CONSTRAINT (if exists)
-- ============================================================================

-- Check if we need to update the valid_modules constraint on batch_scan_jobs
-- This adds 'waymore' to the list of valid module names

DO $$
DECLARE
    constraint_exists BOOLEAN;
BEGIN
    -- Check if the constraint exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'batch_scan_jobs_module_check'
        AND table_name = 'batch_scan_jobs'
    ) INTO constraint_exists;
    
    IF constraint_exists THEN
        -- Drop old constraint
        ALTER TABLE batch_scan_jobs DROP CONSTRAINT IF EXISTS batch_scan_jobs_module_check;
        
        -- Add new constraint with waymore included
        ALTER TABLE batch_scan_jobs ADD CONSTRAINT batch_scan_jobs_module_check
            CHECK (module IN ('subfinder', 'dnsx', 'httpx', 'katana', 'nuclei', 'tyvt', 'url-resolver', 'waymore'));
        
        RAISE NOTICE 'Updated batch_scan_jobs_module_check to include waymore';
    ELSE
        RAISE NOTICE 'No module check constraint found, skipping constraint update';
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM scan_module_profiles WHERE module_name = 'waymore') THEN
        RAISE NOTICE 'SUCCESS: waymore module profile created/updated';
    ELSE
        RAISE EXCEPTION 'FAILED: waymore module profile was not created';
    END IF;
END $$;

-- Display the created profile
DO $$
DECLARE
    profile_record RECORD;
BEGIN
    SELECT module_name, version, supports_batching, dependencies, is_active
    INTO profile_record
    FROM scan_module_profiles
    WHERE module_name = 'waymore';
    
    RAISE NOTICE 'Waymore Profile: name=%, version=%, batching=%, deps=%, active=%',
        profile_record.module_name,
        profile_record.version,
        profile_record.supports_batching,
        profile_record.dependencies,
        profile_record.is_active;
END $$;


