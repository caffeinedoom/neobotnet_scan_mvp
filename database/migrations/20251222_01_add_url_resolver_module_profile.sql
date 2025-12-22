-- Migration: Add url-resolver module profile
-- Date: 2025-12-22
-- Description: Registers the URL Resolver module for probing and enriching URLs discovered by Katana, Waymore, etc.

-- Insert url-resolver module profile
INSERT INTO scan_module_profiles (
    module_name,
    version,
    supports_batching,
    max_batch_size,
    resource_scaling,
    estimated_duration_per_domain,
    task_definition_template,
    container_name,
    is_active,
    optimization_hints,
    dependencies
) VALUES (
    'url-resolver',
    '1.0',
    true,
    100,
    '{
        "scaling_notes": "URL Resolver is I/O bound (HTTP requests). Uses httpx SDK for probing. Memory requirements are moderate for storing response data and technology detection.",
        "domain_count_ranges": [
            {
                "cpu": 256,
                "memory": 512,
                "description": "Small batch (1-50 URLs) - Light probing load",
                "max_domains": 50,
                "min_domains": 1
            },
            {
                "cpu": 512,
                "memory": 1024,
                "description": "Medium batch (51-100 URLs) - Standard probing",
                "max_domains": 100,
                "min_domains": 51
            }
        ]
    }'::jsonb,
    5,  -- 5 seconds per URL (fast HTTP probing)
    'neobotnet-v2-dev-url-resolver',
    'url-resolver-scanner',
    true,
    '{
        "description": "Probes URLs discovered by crawlers (Katana, Waymore, GAU) to verify aliveness and extract metadata",
        "dependencies": ["katana"],
        "streams_output": false,
        "consumes_stream": true,
        "requires_asset_id": true,
        "requires_database_fetch": false,
        "input_stream_pattern": "scan:{scan_job_id}:katana:urls",
        "output_table": "urls",
        "ttl_hours": 24,
        "ttl_enabled": true,
        "streaming_notes": "Consumes URLs from Katana Redis stream. Probes each URL, deduplicates by hash, and stores enriched data in urls table. TTL-based re-probing for stale URLs."
    }'::jsonb,
    ARRAY['katana']
)
ON CONFLICT (module_name) DO UPDATE SET
    version = EXCLUDED.version,
    resource_scaling = EXCLUDED.resource_scaling,
    optimization_hints = EXCLUDED.optimization_hints,
    task_definition_template = EXCLUDED.task_definition_template,
    container_name = EXCLUDED.container_name,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- Verify the insert
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM scan_module_profiles WHERE module_name = 'url-resolver') THEN
        RAISE NOTICE 'SUCCESS: url-resolver module profile created/updated';
    ELSE
        RAISE EXCEPTION 'FAILED: url-resolver module profile was not created';
    END IF;
END $$;

