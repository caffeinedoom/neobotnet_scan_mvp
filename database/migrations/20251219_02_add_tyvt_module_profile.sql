-- ============================================================
-- Migration: Register TYVT module in scan_module_profiles
-- Module: TYVT (VirusTotal Domain Scanner)
-- Date: 2025-12-19
-- ============================================================
-- Description:
--   Registers the TYVT module in the scan_module_profiles table
--   for automatic discovery by the scan engine.
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
    'tyvt',
    '1.0',
    true,
    100,  -- Can batch up to 100 subdomains per task
    '{
        "domain_count_ranges": [
            {
                "min_domains": 1,
                "max_domains": 20,
                "cpu": 256,
                "memory": 512,
                "description": "Light scan - few subdomains"
            },
            {
                "min_domains": 21,
                "max_domains": 50,
                "cpu": 512,
                "memory": 1024,
                "description": "Medium scan - typical asset"
            },
            {
                "min_domains": 51,
                "max_domains": 100,
                "cpu": 512,
                "memory": 1024,
                "description": "Heavy scan - large asset"
            }
        ],
        "scaling_notes": "TYVT is I/O bound (VT API calls). Rate limiting is the bottleneck, not CPU."
    }'::jsonb,
    20,  -- 20 seconds per subdomain (VT rate limits to ~4 requests/minute on free tier)
    'neobotnet-v2-dev-tyvt',
    'tyvt-scanner',
    ARRAY['httpx'],  -- Depends on HTTPx (needs resolved subdomains)
    '{
        "requires_database_fetch": true,
        "requires_asset_id": true,
        "streams_output": true,
        "consumes_stream": true,
        "rate_limited": true,
        "external_api": "virustotal",
        "api_key_required": true
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

-- ============================================================
-- Verification
-- ============================================================

-- Verify module was registered
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM scan_module_profiles WHERE module_name = 'tyvt'
    ) THEN
        RAISE EXCEPTION 'TYVT module was not registered successfully';
    END IF;
    RAISE NOTICE 'TYVT module registered successfully';
END $$;

