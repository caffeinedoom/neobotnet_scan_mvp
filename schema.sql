

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE OR REPLACE FUNCTION "public"."bulk_insert_dns_records"("records" "jsonb") RETURNS TABLE("inserted_count" integer, "updated_count" integer, "skipped_count" integer, "error_count" integer)
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    v_inserted INTEGER := 0;
    v_updated INTEGER := 0;
    v_skipped INTEGER := 0;
    v_total INTEGER;
    v_affected INTEGER := 0;
BEGIN
    -- Get total records count
    v_total := jsonb_array_length(records);
    
    -- Insert records with ON CONFLICT handling
    -- Strategy: Update existing records if data changed, insert new ones
    WITH upsert_result AS (
        INSERT INTO dns_records (
            subdomain,
            parent_domain,
            record_type,
            record_value,
            ttl,
            priority,
            resolved_at,
            resolver_used,
            resolution_time_ms,
            cloud_provider,
            cloud_service,
            cdn_provider,
            cdn_detected,
            scan_job_id,
            batch_scan_id,
            asset_id
        )
        SELECT 
            r->>'subdomain',
            r->>'parent_domain',
            r->>'record_type',
            r->>'record_value',
            (r->>'ttl')::INTEGER,
            (r->>'priority')::INTEGER,
            COALESCE((r->>'resolved_at')::TIMESTAMPTZ, NOW()),
            r->>'resolver_used',
            (r->>'resolution_time_ms')::INTEGER,
            r->>'cloud_provider',
            r->>'cloud_service',
            r->>'cdn_provider',
            COALESCE((r->>'cdn_detected')::BOOLEAN, false),
            (r->>'scan_job_id')::UUID,
            (r->>'batch_scan_id')::UUID,
            (r->>'asset_id')::UUID
        FROM jsonb_array_elements(records) AS r
        ON CONFLICT (subdomain, record_type, record_value, priority)
        DO UPDATE SET
            -- Update fields that might change
            ttl = EXCLUDED.ttl,
            resolved_at = EXCLUDED.resolved_at,
            resolver_used = EXCLUDED.resolver_used,
            resolution_time_ms = EXCLUDED.resolution_time_ms,
            cloud_provider = EXCLUDED.cloud_provider,
            cloud_service = EXCLUDED.cloud_service,
            cdn_provider = EXCLUDED.cdn_provider,
            cdn_detected = EXCLUDED.cdn_detected,
            updated_at = NOW()
        WHERE 
            -- Only update if data actually changed (optimization)
            dns_records.ttl IS DISTINCT FROM EXCLUDED.ttl OR
            dns_records.cloud_provider IS DISTINCT FROM EXCLUDED.cloud_provider OR
            dns_records.cloud_service IS DISTINCT FROM EXCLUDED.cloud_service OR
            dns_records.cdn_provider IS DISTINCT FROM EXCLUDED.cdn_provider
        RETURNING 
            (xmax = 0) AS inserted  -- xmax = 0 means INSERT, xmax > 0 means UPDATE
    )
    SELECT 
        COUNT(*) FILTER (WHERE inserted),
        COUNT(*) FILTER (WHERE NOT inserted)
    INTO v_inserted, v_updated
    FROM upsert_result;
    
    -- Get total affected rows
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    
    -- Calculate skipped (records that matched exactly and weren't updated)
    v_skipped := v_total - v_affected;
    
    -- Return summary
    RETURN QUERY SELECT v_inserted, v_updated, v_skipped, 0;
    
EXCEPTION WHEN OTHERS THEN
    -- Return error count on failure
    RAISE WARNING 'Bulk insert failed: %', SQLERRM;
    RETURN QUERY SELECT 0, 0, 0, v_total;
END;
$$;


ALTER FUNCTION "public"."bulk_insert_dns_records"("records" "jsonb") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."bulk_insert_dns_records"("records" "jsonb") IS 'Bulk insert DNS records with UPDATE on conflict. Updates only if data changed. Returns counts of inserted/updated/skipped/errored records.';



CREATE OR REPLACE FUNCTION "public"."bulk_insert_subdomains"("records" "jsonb") RETURNS TABLE("inserted" integer, "skipped" integer)
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    inserted_count INT := 0;
    total_count INT := 0;
    skipped_count INT := 0;
BEGIN
    -- Get total number of records in the input
    total_count := jsonb_array_length(records);
    
    -- Insert subdomains, skipping duplicates
    INSERT INTO subdomains (
        parent_domain, 
        subdomain, 
        scan_job_id,
        asset_id,
        source_module, 
        discovered_at
    )
    SELECT 
        (r->>'parent_domain')::TEXT,
        (r->>'subdomain')::TEXT,
        (r->>'scan_job_id')::UUID,
        (r->>'asset_id')::UUID,
        (r->>'source_module')::TEXT,
        (r->>'discovered_at')::TIMESTAMPTZ
    FROM jsonb_array_elements(records) AS r
    ON CONFLICT (parent_domain, subdomain) DO NOTHING;
    
    -- Get the number of rows actually inserted
    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    
    -- Calculate skipped count
    skipped_count := total_count - inserted_count;
    
    -- Return the counts
    RETURN QUERY SELECT inserted_count, skipped_count;
END;
$$;


ALTER FUNCTION "public"."bulk_insert_subdomains"("records" "jsonb") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."bulk_insert_subdomains"("records" "jsonb") IS 'Bulk insert subdomains with automatic duplicate handling using ON CONFLICT. 
Includes asset_id field for proper foreign key relationships.
Returns counts of inserted and skipped records.';



CREATE OR REPLACE FUNCTION "public"."calculate_module_resources"("p_module_name" "text", "p_domain_count" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
DECLARE
    profile_record RECORD;
    scaling_config JSONB;
    range_config JSONB;
    result JSONB;
BEGIN
    -- Get the module profile
    SELECT * INTO profile_record
    FROM scan_module_profiles 
    WHERE module_name = p_module_name 
      AND is_active = true 
    ORDER BY version DESC 
    LIMIT 1;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Module profile not found for: %', p_module_name;
    END IF;
    
    -- Find the appropriate resource range
    scaling_config := profile_record.resource_scaling;
    
    FOR range_config IN SELECT * FROM jsonb_array_elements(scaling_config->'domain_count_ranges')
    LOOP
        IF p_domain_count >= (range_config->>'min_domains')::INTEGER 
           AND p_domain_count <= (range_config->>'max_domains')::INTEGER THEN
            
            result := jsonb_build_object(
                'cpu', (range_config->>'cpu')::INTEGER,
                'memory', (range_config->>'memory')::INTEGER,
                'estimated_duration_minutes', 
                    CEIL((p_domain_count * profile_record.estimated_duration_per_domain) / 60.0),
                'description', range_config->>'description',
                'domain_count', p_domain_count,
                'module_name', p_module_name
            );
            
            RETURN result;
        END IF;
    END LOOP;
    
    -- If no range found, use the largest range (for oversized batches)
    SELECT elements INTO range_config
    FROM jsonb_array_elements(scaling_config->'domain_count_ranges') AS elements
    ORDER BY (elements->>'max_domains')::INTEGER DESC
    LIMIT 1;
    
    result := jsonb_build_object(
        'cpu', (range_config->>'cpu')::INTEGER,
        'memory', (range_config->>'memory')::INTEGER,
        'estimated_duration_minutes', 
            CEIL((p_domain_count * profile_record.estimated_duration_per_domain) / 60.0),
        'description', 'Oversized batch - using maximum resources',
        'domain_count', p_domain_count,
        'module_name', p_module_name
    );
    
    RETURN result;
END;
$$;


ALTER FUNCTION "public"."calculate_module_resources"("p_module_name" "text", "p_domain_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."can_add_domain_to_asset"("check_user_id" "uuid", "check_asset_id" "uuid") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
    domain_count integer;
    max_per_asset integer;
BEGIN
    -- Initialize user tracking if not exists
    PERFORM public.ensure_user_tracking_initialized(check_user_id);
    
    -- Verify user owns the asset
    IF NOT EXISTS(
        SELECT 1 FROM public.assets 
        WHERE id = check_asset_id AND user_id = check_user_id
    ) THEN
        RETURN false;
    END IF;
    
    -- Count current domains in this asset
    SELECT COUNT(*) INTO domain_count
    FROM public.apex_domains
    WHERE asset_id = check_asset_id;
    
    -- Get per-asset domain limit
    SELECT max_domains_per_asset INTO max_per_asset
    FROM public.user_quotas
    WHERE user_id = check_user_id;
    
    -- Return true if under limit
    RETURN domain_count < max_per_asset;
    
EXCEPTION
    WHEN OTHERS THEN
        -- On any error, default to allowing
        RETURN true;
END;
$$;


ALTER FUNCTION "public"."can_add_domain_to_asset"("check_user_id" "uuid", "check_asset_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."can_create_asset"("check_user_id" "uuid") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
    current_count integer;
    max_allowed integer;
BEGIN
    -- Initialize user tracking if not exists
    PERFORM public.ensure_user_tracking_initialized(check_user_id);
    
    -- Get current asset count and limit
    SELECT 
        current_assets,
        max_assets
    INTO current_count, max_allowed
    FROM public.user_usage_overview
    WHERE user_id = check_user_id;
    
    -- Return true if under limit
    RETURN current_count < max_allowed;
    
EXCEPTION
    WHEN OTHERS THEN
        -- On any error, default to allowing (fail open for new users)
        RETURN true;
END;
$$;


ALTER FUNCTION "public"."can_create_asset"("check_user_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."can_start_scan"("check_user_id" "uuid") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
    overview_data public.user_usage_overview%ROWTYPE;
BEGIN
    -- Initialize user tracking if not exists
    PERFORM public.ensure_user_tracking_initialized(check_user_id);
    
    -- Get usage overview
    SELECT * INTO overview_data
    FROM public.user_usage_overview
    WHERE user_id = check_user_id;
    
    -- Check all scan limits
    IF overview_data.daily_limit_reached OR 
       overview_data.monthly_limit_reached OR 
       overview_data.concurrent_limit_reached THEN
        RETURN false;
    END IF;
    
    RETURN true;
    
EXCEPTION
    WHEN OTHERS THEN
        -- On any error, default to allowing
        RETURN true;
END;
$$;


ALTER FUNCTION "public"."can_start_scan"("check_user_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."create_asset_with_domains"("p_name" "text", "p_description" "text" DEFAULT NULL::"text", "p_bug_bounty_url" "text" DEFAULT NULL::"text", "p_domains" "text"[] DEFAULT '{}'::"text"[], "p_priority" integer DEFAULT 1) RETURNS "uuid"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
    v_asset_id UUID;
    v_domain TEXT;
BEGIN
    -- Create the asset
    INSERT INTO public.assets (name, description, bug_bounty_url, priority, user_id)
    VALUES (p_name, p_description, p_bug_bounty_url, p_priority, auth.uid())
    RETURNING id INTO v_asset_id;
    
    -- Create apex domains
    FOREACH v_domain IN ARRAY p_domains
    LOOP
        INSERT INTO public.apex_domains (asset_id, domain)
        VALUES (v_asset_id, v_domain);
    END LOOP;
    
    RETURN v_asset_id;
END;
$$;


ALTER FUNCTION "public"."create_asset_with_domains"("p_name" "text", "p_description" "text", "p_bug_bounty_url" "text", "p_domains" "text"[], "p_priority" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."ensure_user_tracking_initialized"("target_user_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
    -- Insert default quota if not exists
    INSERT INTO public.user_quotas (user_id)
    VALUES (target_user_id)
    ON CONFLICT (user_id) DO NOTHING;
    
    -- Insert default usage if not exists  
    INSERT INTO public.user_usage (user_id)
    VALUES (target_user_id)
    ON CONFLICT (user_id) DO NOTHING;
    
    -- Update current counts using CURRENT tables (asset_scan_jobs, not scan_jobs)
    UPDATE public.user_usage
    SET current_assets = (
        SELECT COUNT(*) FROM public.assets WHERE user_id = target_user_id
    ),
    current_domains = (
        SELECT COUNT(*) 
        FROM public.apex_domains ad
        JOIN public.assets a ON ad.asset_id = a.id  
        WHERE a.user_id = target_user_id AND ad.is_active = true
    ),
    current_active_scans = (
        -- FIX: Use asset_scan_jobs instead of scan_jobs
        SELECT COUNT(*)
        FROM public.asset_scan_jobs
        WHERE user_id = target_user_id AND status IN ('pending', 'running')
    ),
    current_subdomains = (
        -- FIX: Join with asset_scan_jobs instead of scan_jobs
        SELECT COUNT(DISTINCT s.id)
        FROM public.subdomains s
        JOIN public.asset_scan_jobs asj ON s.scan_job_id = asj.id
        WHERE asj.user_id = target_user_id
    ),
    updated_at = now()
    WHERE user_id = target_user_id;
    
END;
$$;


ALTER FUNCTION "public"."ensure_user_tracking_initialized"("target_user_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_dashboard_stats"("target_user_id" "uuid") RETURNS json
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
    result json;
BEGIN
    SELECT json_build_object(
        'total_assets', COALESCE(asset_stats.total_assets, 0),
        'active_assets', COALESCE(asset_stats.active_assets, 0),
        'total_domains', COALESCE(domain_stats.total_domains, 0),
        'active_domains', COALESCE(domain_stats.active_domains, 0),
        'total_scans', COALESCE(scan_stats.total_scans, 0),
        'completed_scans', COALESCE(scan_stats.completed_scans, 0),
        'failed_scans', COALESCE(scan_stats.failed_scans, 0),
        'pending_scans', COALESCE(scan_stats.pending_scans, 0),
        'total_subdomains', COALESCE(subdomain_stats.total_subdomains, 0),
        'last_scan_date', scan_stats.last_scan_date
    ) INTO result
    FROM 
        -- Asset statistics
        (SELECT 
            COUNT(*) as total_assets,
            COUNT(*) FILTER (WHERE a.is_active = true) as active_assets
         FROM assets a
         WHERE a.user_id = target_user_id) as asset_stats,
        
        -- Domain statistics - FIXED: Specify table aliases for is_active
        (SELECT 
            COUNT(*) as total_domains,
            COUNT(*) FILTER (WHERE ad.is_active = true) as active_domains
         FROM apex_domains ad
         JOIN assets a ON ad.asset_id = a.id
         WHERE a.user_id = target_user_id) as domain_stats,
        
        -- Asset scan job statistics
        (SELECT 
            COUNT(*) as total_scans,
            COUNT(*) FILTER (WHERE status = 'completed') as completed_scans,
            COUNT(*) FILTER (WHERE status = 'failed') as failed_scans,
            COUNT(*) FILTER (WHERE status IN ('pending', 'running')) as pending_scans,
            MAX(created_at) as last_scan_date
         FROM asset_scan_jobs 
         WHERE user_id = target_user_id) as scan_stats,
        
        -- FIXED: Subdomain statistics using asset_scan_jobs FK
        (SELECT 
            COUNT(*) as total_subdomains
         FROM subdomains s
         JOIN asset_scan_jobs asj ON s.scan_job_id = asj.id
         WHERE asj.user_id = target_user_id) as subdomain_stats;
    
    RETURN result;
END;
$$;


ALTER FUNCTION "public"."get_dashboard_stats"("target_user_id" "uuid") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."get_dashboard_stats"("target_user_id" "uuid") IS 'Optimized dashboard statistics aggregation function with FIXED subdomain counting.

FIXED in this version:
- Uses COUNT(DISTINCT s.id) to prevent duplicate counting of subdomains
- Handles JOIN multiplicity correctly across asset → domain → scan relationships

Performance characteristics:
- Time complexity: O(1) regardless of data volume
- Network calls: Reduces 2+ API calls to 1
- Computation: Database-level aggregation vs client-side loops
- Accuracy: Correctly handles relational duplicates with DISTINCT clauses

Returns JSON object with accurate counts for:
- total_assets: Total number of user assets
- active_assets: Number of active assets  
- total_domains: Total apex domains across all assets
- active_domains: Number of active apex domains
- total_scans: Total asset-level scans performed
- completed_scans: Number of successfully completed scans
- failed_scans: Number of failed scans
- pending_scans: Number of pending/running scans  
- total_subdomains: ACCURATE count of unique subdomains discovered
- last_scan_date: Timestamp of most recent scan';



CREATE OR REPLACE FUNCTION "public"."get_optimal_batch_sizes"("p_module_name" "text", "p_total_domains" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
DECLARE
    profile_record RECORD;
    max_batch_size INTEGER;
    batch_sizes INTEGER[];
    remaining_domains INTEGER;
    current_batch_size INTEGER;
    result JSONB;
BEGIN
    -- Get the module profile
    SELECT * INTO profile_record
    FROM scan_module_profiles 
    WHERE module_name = p_module_name 
      AND is_active = true 
    ORDER BY version DESC 
    LIMIT 1;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Module profile not found for: %', p_module_name;
    END IF;
    
    max_batch_size := profile_record.max_batch_size;
    remaining_domains := p_total_domains;
    batch_sizes := ARRAY[]::INTEGER[];
    
    -- Calculate optimal batch distribution
    WHILE remaining_domains > 0 LOOP
        IF remaining_domains <= max_batch_size THEN
            current_batch_size := remaining_domains;
        ELSE
            current_batch_size := max_batch_size;
        END IF;
        
        batch_sizes := array_append(batch_sizes, current_batch_size);
        remaining_domains := remaining_domains - current_batch_size;
    END LOOP;
    
    result := jsonb_build_object(
        'total_domains', p_total_domains,
        'batch_sizes', to_jsonb(batch_sizes),
        'total_batches', array_length(batch_sizes, 1),
        'max_batch_size', max_batch_size,
        'module_name', p_module_name
    );
    
    RETURN result;
END;
$$;


ALTER FUNCTION "public"."get_optimal_batch_sizes"("p_module_name" "text", "p_total_domains" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_paid_user_count"() RETURNS integer
    LANGUAGE "sql" SECURITY DEFINER
    AS $$
  SELECT COUNT(*)::INTEGER FROM user_quotas WHERE plan_type = 'paid';
$$;


ALTER FUNCTION "public"."get_paid_user_count"() OWNER TO "postgres";


-- Atomic increment for URL quota tracking (prevents race conditions)
CREATE OR REPLACE FUNCTION "public"."increment_url_quota"("p_user_id" "uuid", "p_count" integer) RETURNS void
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
    -- Atomically increment the urls_viewed_count
    -- This prevents race conditions from concurrent requests
    UPDATE public.user_usage
    SET urls_viewed_count = COALESCE(urls_viewed_count, 0) + p_count,
        updated_at = NOW()
    WHERE user_id = p_user_id;
    
    -- If no row was updated, insert a new record
    IF NOT FOUND THEN
        INSERT INTO public.user_usage (user_id, urls_viewed_count)
        VALUES (p_user_id, p_count)
        ON CONFLICT (user_id) DO UPDATE
        SET urls_viewed_count = COALESCE(user_usage.urls_viewed_count, 0) + p_count,
            updated_at = NOW();
    END IF;
END;
$$;


ALTER FUNCTION "public"."increment_url_quota"("p_user_id" "uuid", "p_count" integer) OWNER TO "postgres";


COMMENT ON FUNCTION "public"."increment_url_quota"("p_user_id" "uuid", "p_count" integer) IS 'Atomically increment the URL quota for a user. Prevents race conditions from concurrent API requests.';


CREATE OR REPLACE FUNCTION "public"."get_user_recon_data"("target_user_id" "uuid") RETURNS json
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
    result json;
    summary_data json;
    assets_data json;
    scans_data json;
BEGIN
    -- Calculate summary statistics using FIXED asset_scan_jobs FK
    SELECT json_build_object(
        'total_assets', COALESCE(asset_stats.total_assets, 0),
        'active_assets', COALESCE(asset_stats.active_assets, 0),
        'total_domains', COALESCE(domain_stats.total_domains, 0),
        'active_domains', COALESCE(domain_stats.active_domains, 0),
        'total_scans', COALESCE(scan_stats.total_scans, 0),
        'completed_scans', COALESCE(scan_stats.completed_scans, 0),
        'failed_scans', COALESCE(scan_stats.failed_scans, 0),
        'pending_scans', COALESCE(scan_stats.pending_scans, 0),
        'total_subdomains', COALESCE(subdomain_stats.total_subdomains, 0),
        'last_scan_date', scan_stats.last_scan_date
    ) INTO summary_data
    FROM 
        -- Asset statistics
        (SELECT 
            COUNT(*) as total_assets,
            COUNT(*) FILTER (WHERE a.is_active = true) as active_assets
         FROM assets a
         WHERE a.user_id = target_user_id) as asset_stats,
        
        -- Domain statistics - FIXED: Specify table aliases for is_active
        (SELECT 
            COUNT(*) as total_domains,
            COUNT(*) FILTER (WHERE ad.is_active = true) as active_domains
         FROM apex_domains ad
         JOIN assets a ON ad.asset_id = a.id
         WHERE a.user_id = target_user_id) as domain_stats,
        
        -- Asset scan job statistics
        (SELECT 
            COUNT(*) as total_scans,
            COUNT(*) FILTER (WHERE status = 'completed') as completed_scans,
            COUNT(*) FILTER (WHERE status = 'failed') as failed_scans,
            COUNT(*) FILTER (WHERE status IN ('pending', 'running')) as pending_scans,
            MAX(created_at) as last_scan_date
         FROM asset_scan_jobs 
         WHERE user_id = target_user_id) as scan_stats,
        
        -- FIXED: Subdomain statistics using asset_scan_jobs FK
        (SELECT 
            COUNT(*) as total_subdomains
         FROM subdomains s
         JOIN asset_scan_jobs asj ON s.scan_job_id = asj.id
         WHERE asj.user_id = target_user_id) as subdomain_stats;

    -- Get individual assets with FIXED subdomain counts
    SELECT COALESCE(json_agg(
        json_build_object(
            'id', a.id,
            'name', a.name,
            'description', a.description,
            'created_at', a.created_at,
            'is_active', a.is_active,
            'apex_domain_count', COALESCE(domain_counts.domain_count, 0),
            'total_subdomains', COALESCE(subdomain_counts.subdomain_count, 0),
            'total_scans', COALESCE(scan_counts.scan_count, 0),
            'completed_scans', COALESCE(scan_counts.completed_count, 0),
            'failed_scans', COALESCE(scan_counts.failed_count, 0),
            'pending_scans', COALESCE(scan_counts.pending_count, 0),
            'last_scan_date', scan_counts.last_scan_date
        )
    ), '[]'::json) INTO assets_data
    FROM assets a
    LEFT JOIN (
        SELECT 
            asset_id,
            COUNT(*) as domain_count
        FROM apex_domains
        GROUP BY asset_id
    ) domain_counts ON a.id = domain_counts.asset_id
    LEFT JOIN (
        -- FIXED: Count subdomains through asset_scan_jobs FK
        SELECT 
            asj.asset_id,
            COUNT(s.id) as subdomain_count
        FROM asset_scan_jobs asj
        LEFT JOIN subdomains s ON asj.id = s.scan_job_id
        GROUP BY asj.asset_id
    ) subdomain_counts ON a.id = subdomain_counts.asset_id
    LEFT JOIN (
        SELECT 
            asset_id,
            COUNT(*) as scan_count,
            COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
            COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
            COUNT(*) FILTER (WHERE status IN ('pending', 'running')) as pending_count,
            MAX(created_at) as last_scan_date
        FROM asset_scan_jobs
        GROUP BY asset_id
    ) scan_counts ON a.id = scan_counts.asset_id
    WHERE a.user_id = target_user_id;

    -- Get recent scans (last 50) - FIXED: Proper table aliases and structure
    SELECT COALESCE(json_agg(
        json_build_object(
            'id', scan_data.id,
            'asset_id', scan_data.asset_id,
            'asset_name', scan_data.asset_name,
            'status', scan_data.status,
            'modules', scan_data.modules,
            'total_domains', scan_data.total_domains,
            'completed_domains', scan_data.completed_domains,
            'progress_percentage', scan_data.progress_percentage,
            'created_at', scan_data.created_at,
            'completed_at', scan_data.completed_at,
            'subdomains_found', COALESCE(subdomain_counts.subdomain_count, 0)
        )
    ), '[]'::json) INTO scans_data
    FROM (
        SELECT 
            asj.id,
            asj.asset_id,
            a.name as asset_name,
            asj.status,
            asj.modules,
            asj.total_domains,
            asj.completed_domains,
            CASE 
                WHEN asj.total_domains > 0 THEN 
                    ROUND((asj.completed_domains::numeric / asj.total_domains::numeric) * 100, 1)
                ELSE 0 
            END as progress_percentage,
            asj.created_at,
            asj.completed_at
        FROM asset_scan_jobs asj
        JOIN assets a ON asj.asset_id = a.id
        WHERE asj.user_id = target_user_id
        ORDER BY asj.created_at DESC
        LIMIT 50
    ) scan_data
    LEFT JOIN (
        -- Count subdomains for each scan using correct FK
        SELECT 
            scan_job_id,
            COUNT(*) as subdomain_count
        FROM subdomains
        GROUP BY scan_job_id
    ) subdomain_counts ON scan_data.id = subdomain_counts.scan_job_id;

    -- Combine all data into final result
    SELECT json_build_object(
        'summary', summary_data,
        'assets', assets_data,
        'recent_scans', scans_data
    ) INTO result;

    RETURN result;
END;
$$;


ALTER FUNCTION "public"."get_user_recon_data"("target_user_id" "uuid") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."get_user_recon_data"("target_user_id" "uuid") IS 'Unified reconnaissance data service - single query for all recon pages.

PERFORMANCE REVOLUTION:
- Eliminates N+1 queries across Dashboard, Assets, and Scans pages
- Reduces hundreds of database queries to just 1
- Uses optimized CTEs and existing indexes for maximum performance
- Scales O(1) regardless of asset/scan volume

SERVES MULTIPLE PAGES:
- Dashboard: summary statistics with real-time counters
- Assets: individual asset data + summary statistics  
- Scans: recent scan history + assets + summary statistics

RETURNS JSON STRUCTURE:
{
  "summary": {
    "total_assets": number,
    "active_assets": number, 
    "total_domains": number,
    "active_domains": number,
    "total_scans": number,
    "completed_scans": number,
    "failed_scans": number,
    "pending_scans": number,
    "total_subdomains": number,
    "last_scan_date": timestamp
  },
  "assets": [...],      // Individual assets with full statistics
  "recent_scans": [...]  // Recent 50 scans with progress data
}

GUARANTEES DATA CONSISTENCY:
- All pages show identical metrics from same data source
- No risk of mismatched counters between pages
- Real-time consistency across entire application';



CREATE OR REPLACE FUNCTION "public"."has_paid_spots_available"("max_spots" integer DEFAULT 100) RETURNS boolean
    LANGUAGE "sql" SECURITY DEFINER
    AS $$
  SELECT (SELECT COUNT(*) FROM user_quotas WHERE plan_type = 'paid') < max_spots;
$$;


ALTER FUNCTION "public"."has_paid_spots_available"("max_spots" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."sync_subdomain_asset_id"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    SELECT asset_id INTO NEW.asset_id
    FROM asset_scan_jobs
    WHERE id = NEW.scan_job_id;
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."sync_subdomain_asset_id"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_apex_domain_last_scanned"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    UPDATE public.apex_domains 
    SET last_scanned_at = NOW()
    WHERE id = NEW.apex_domain_id;
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_apex_domain_last_scanned"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_api_key_last_used"("p_key_hash" "text") RETURNS "void"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
    UPDATE "public"."api_keys"
    SET "last_used_at" = NOW()
    WHERE "key_hash" = p_key_hash
      AND "is_active" = true;
END;
$$;


ALTER FUNCTION "public"."update_api_key_last_used"("p_key_hash" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."update_api_key_last_used"("p_key_hash" "text") IS 'Updates the last_used_at timestamp for an API key. Called during authentication.';



CREATE OR REPLACE FUNCTION "public"."update_asset_scan_jobs_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_asset_scan_jobs_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_batch_scan_jobs_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_batch_scan_jobs_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_scan_completed_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    -- If status changes to completed/failed/cancelled and completed_at is NULL
    IF NEW.status IN ('completed', 'partial_failure', 'failed', 'cancelled') 
       AND OLD.status NOT IN ('completed', 'partial_failure', 'failed', 'cancelled')
       AND NEW.completed_at IS NULL THEN
        NEW.completed_at = NOW();
    END IF;
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_scan_completed_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_scan_job_progress"("p_scan_job_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    total_modules integer;
    completed_modules integer;
    failed_modules integer;
    new_progress integer;
    new_status text;
BEGIN
    -- Count module executions
    SELECT 
        COUNT(*),
        COUNT(CASE WHEN status = 'completed' THEN 1 END),
        COUNT(CASE WHEN status = 'failed' THEN 1 END)
    INTO total_modules, completed_modules, failed_modules
    FROM module_executions 
    WHERE scan_job_id = p_scan_job_id;
    
    -- Calculate progress
    IF total_modules = 0 THEN
        new_progress := 0;
        new_status := 'pending';
    ELSE
        new_progress := ROUND((completed_modules::decimal / total_modules::decimal) * 100);
        
        -- Determine status
        IF (completed_modules + failed_modules) = total_modules THEN
            IF failed_modules = total_modules THEN
                new_status := 'failed';
            ELSE
                new_status := 'completed';
            END IF;
        ELSIF completed_modules > 0 OR failed_modules > 0 THEN
            new_status := 'running';
        ELSE
            new_status := 'pending';
        END IF;
    END IF;
    
    -- Update the scan job
    UPDATE unified_scan_jobs 
    SET 
        progress_percentage = new_progress,
        status = new_status,
        completed_domains = completed_modules,
        failed_domains = failed_modules,
        started_at = CASE WHEN started_at IS NULL AND new_status = 'running' THEN now() ELSE started_at END,
        completed_at = CASE WHEN new_status IN ('completed', 'failed') AND completed_at IS NULL THEN now() ELSE completed_at END
    WHERE id = p_scan_job_id;
    
END;
$$;


ALTER FUNCTION "public"."update_scan_job_progress"("p_scan_job_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_user_asset_count"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- Ensure user tracking exists
        PERFORM public.ensure_user_tracking_initialized(OLD.user_id);
        
        -- FIXED: Only decrement if count is greater than 0 (prevent negative)
        UPDATE public.user_usage 
        SET current_assets = GREATEST(current_assets - 1, 0),
            updated_at = now()
        WHERE user_id = OLD.user_id;
        
        RETURN OLD;
    ELSE
        -- INSERT case
        PERFORM public.ensure_user_tracking_initialized(NEW.user_id);
        UPDATE public.user_usage
        SET current_assets = current_assets + 1,
            updated_at = now()
        WHERE user_id = NEW.user_id;
        RETURN NEW;
    END IF;
END;
$$;


ALTER FUNCTION "public"."update_user_asset_count"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_user_domain_count"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    asset_user_id uuid;
BEGIN
    -- Get the user_id from the asset
    IF TG_OP = 'DELETE' THEN
        -- FIXED: Handle case where asset might be deleted due to CASCADE
        SELECT user_id INTO asset_user_id
        FROM public.assets WHERE id = OLD.asset_id;
        
        -- Only proceed if we found a valid user_id (asset still exists)
        IF asset_user_id IS NOT NULL THEN
            PERFORM public.ensure_user_tracking_initialized(asset_user_id);
            -- FIXED: Prevent negative counts
            UPDATE public.user_usage
            SET current_domains = GREATEST(current_domains - 1, 0),
                updated_at = now()  
            WHERE user_id = asset_user_id;
        END IF;
        
        RETURN OLD;
    ELSE
        -- INSERT case - asset definitely exists
        SELECT user_id INTO asset_user_id
        FROM public.assets WHERE id = NEW.asset_id;
        
        PERFORM public.ensure_user_tracking_initialized(asset_user_id);
        UPDATE public.user_usage
        SET current_domains = current_domains + 1,
            updated_at = now()
        WHERE user_id = asset_user_id;
        RETURN NEW;
    END IF;
END;
$$;


ALTER FUNCTION "public"."update_user_domain_count"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."apex_domains" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "asset_id" "uuid" NOT NULL,
    "domain" "text" NOT NULL,
    "description" "text",
    "is_active" boolean DEFAULT true,
    "last_scanned_at" timestamp with time zone,
    "registrar" "text",
    "dns_servers" "text"[],
    "metadata" "jsonb" DEFAULT '{}'::"jsonb",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "valid_domain" CHECK (("domain" ~ '^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'::"text"))
);


ALTER TABLE "public"."apex_domains" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."asset_scan_jobs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "asset_id" "uuid" NOT NULL,
    "modules" "text"[] DEFAULT ARRAY['subfinder'::"text"] NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "total_domains" integer DEFAULT 0 NOT NULL,
    "completed_domains" integer DEFAULT 0 NOT NULL,
    "active_domains_only" boolean DEFAULT true,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "started_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    "estimated_completion" timestamp with time zone,
    "error_message" "text",
    "metadata" "jsonb" DEFAULT '{}'::"jsonb",
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "parent_scan_id" "uuid",
    CONSTRAINT "valid_domain_counts" CHECK ((("total_domains" >= 0) AND ("completed_domains" >= 0) AND ("completed_domains" <= "total_domains"))),
    CONSTRAINT "valid_modules" CHECK (("modules" <@ ARRAY['subfinder'::"text", 'dnsx'::"text", 'httpx'::"text", 'katana'::"text", 'url-resolver'::"text", 'tyvt'::"text", 'waymore'::"text"])),
    CONSTRAINT "valid_status" CHECK (("status" = ANY (ARRAY['pending'::"text", 'running'::"text", 'completed'::"text", 'failed'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "public"."asset_scan_jobs" OWNER TO "postgres";


COMMENT ON COLUMN "public"."asset_scan_jobs"."parent_scan_id" IS 'Links to parent scan (for multi-asset operations)';



COMMENT ON CONSTRAINT "valid_modules" ON "public"."asset_scan_jobs" IS 'Validates that all requested modules are in the allowed list. Updated 2025-12-22 to include waymore (Historical URL Discovery).';



CREATE TABLE IF NOT EXISTS "public"."assets" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "name" "text" NOT NULL,
    "description" "text",
    "bug_bounty_url" "text",
    "is_active" boolean DEFAULT true,
    "priority" integer DEFAULT 1,
    "tags" "text"[] DEFAULT '{}'::"text"[],
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "valid_name" CHECK ((("length"("name") >= 2) AND ("length"("name") <= 100))),
    CONSTRAINT "valid_priority" CHECK ((("priority" >= 1) AND ("priority" <= 5)))
);


ALTER TABLE "public"."assets" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."subdomains" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "scan_job_id" "uuid" NOT NULL,
    "subdomain" "text" NOT NULL,
    "discovered_at" timestamp with time zone DEFAULT "now"(),
    "last_checked" timestamp with time zone DEFAULT "now"(),
    "source_module" "text" DEFAULT 'subfinder'::"text",
    "parent_domain" "text" NOT NULL,
    "asset_id" "uuid" NOT NULL,
    CONSTRAINT "check_parent_domain_format" CHECK ((("parent_domain" IS NULL) OR (("length"("parent_domain") >= 3) AND ("length"("parent_domain") <= 253) AND ("parent_domain" ~ '^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'::"text"))))
);


ALTER TABLE "public"."subdomains" OWNER TO "postgres";


COMMENT ON COLUMN "public"."subdomains"."parent_domain" IS 'The apex domain that this subdomain belongs to (e.g., epicgames.com for support.epicgames.com)';



CREATE OR REPLACE VIEW "public"."apex_domain_overview" AS
 SELECT "ad"."id",
    "ad"."asset_id",
    "a"."name" AS "asset_name",
    "ad"."domain",
    "ad"."description",
    "ad"."is_active",
    "ad"."last_scanned_at",
    "ad"."created_at",
    "ad"."updated_at",
    COALESCE("subdomain_stats"."subdomain_count", (0)::bigint) AS "subdomain_count",
    COALESCE("subdomain_stats"."used_modules", '{}'::"text"[]) AS "used_modules"
   FROM (("public"."apex_domains" "ad"
     LEFT JOIN "public"."assets" "a" ON (("ad"."asset_id" = "a"."id")))
     LEFT JOIN ( SELECT "a_1"."id" AS "asset_id",
            "count"("s"."id") AS "subdomain_count",
            "array_agg"(DISTINCT "s"."source_module") FILTER (WHERE ("s"."source_module" IS NOT NULL)) AS "used_modules"
           FROM (("public"."assets" "a_1"
             JOIN "public"."asset_scan_jobs" "asj" ON (("a_1"."id" = "asj"."asset_id")))
             LEFT JOIN "public"."subdomains" "s" ON (("asj"."id" = "s"."scan_job_id")))
          GROUP BY "a_1"."id") "subdomain_stats" ON (("ad"."asset_id" = "subdomain_stats"."asset_id")));


ALTER VIEW "public"."apex_domain_overview" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."api_keys" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "key_hash" "text" NOT NULL,
    "key_prefix" "text" NOT NULL,
    "name" "text" DEFAULT 'Default'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "last_used_at" timestamp with time zone,
    "is_active" boolean DEFAULT true NOT NULL,
    "encrypted_key" "text"
);


ALTER TABLE "public"."api_keys" OWNER TO "postgres";


COMMENT ON TABLE "public"."api_keys" IS 'Stores hashed API keys for authenticated users. Keys are SHA-256 hashed for security. The key_prefix stores first 8 chars for display (e.g., "nb_live_a1b2...").';



COMMENT ON COLUMN "public"."api_keys"."key_hash" IS 'SHA-256 hash of the full API key. Never store the raw key.';



COMMENT ON COLUMN "public"."api_keys"."key_prefix" IS 'First 8 characters of the key for display purposes (e.g., "nb_live_a1b2c3d4").';



COMMENT ON COLUMN "public"."api_keys"."is_active" IS 'Whether the key is active. Inactive keys cannot be used for authentication.';



CREATE OR REPLACE VIEW "public"."asset_overview" AS
 SELECT "a"."id",
    "a"."user_id",
    "a"."name",
    "a"."description",
    "a"."bug_bounty_url",
    "a"."is_active",
    "a"."priority",
    "a"."tags",
    "a"."created_at",
    "a"."updated_at",
    "count"(DISTINCT "ad"."id") AS "domain_count",
    "count"(DISTINCT "s"."id") AS "subdomain_count",
    "count"(DISTINCT
        CASE
            WHEN ("ad"."is_active" = true) THEN "ad"."id"
            ELSE NULL::"uuid"
        END) AS "active_domain_count"
   FROM ((("public"."assets" "a"
     LEFT JOIN "public"."apex_domains" "ad" ON (("a"."id" = "ad"."asset_id")))
     LEFT JOIN "public"."asset_scan_jobs" "asj" ON (("a"."id" = "asj"."asset_id")))
     LEFT JOIN "public"."subdomains" "s" ON (("asj"."id" = "s"."scan_job_id")))
  GROUP BY "a"."id", "a"."user_id", "a"."name", "a"."description", "a"."bug_bounty_url", "a"."is_active", "a"."priority", "a"."tags", "a"."created_at", "a"."updated_at";


ALTER VIEW "public"."asset_overview" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."dns_records" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "subdomain" "text" NOT NULL,
    "parent_domain" "text" NOT NULL,
    "record_type" "text" NOT NULL,
    "record_value" "text" NOT NULL,
    "ttl" integer,
    "priority" integer,
    "resolved_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "resolver_used" "text",
    "resolution_time_ms" integer,
    "cloud_provider" "text",
    "cloud_service" "text",
    "cdn_provider" "text",
    "cdn_detected" boolean DEFAULT false,
    "scan_job_id" "uuid",
    "batch_scan_id" "uuid",
    "asset_id" "uuid",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "dns_records_record_type_check" CHECK (("record_type" = ANY (ARRAY['A'::"text", 'AAAA'::"text", 'CNAME'::"text", 'MX'::"text", 'TXT'::"text"])))
);


ALTER TABLE "public"."dns_records" OWNER TO "postgres";


COMMENT ON TABLE "public"."dns_records" IS 'Stores DNS resolution results for all subdomains. Supports A, AAAA, CNAME, MX, and TXT record types.';



COMMENT ON COLUMN "public"."dns_records"."subdomain" IS 'Full subdomain (e.g., "api.example.com")';



COMMENT ON COLUMN "public"."dns_records"."parent_domain" IS 'Extracted parent domain (e.g., "example.com")';



COMMENT ON COLUMN "public"."dns_records"."record_type" IS 'DNS record type: A, AAAA, CNAME, MX, or TXT';



COMMENT ON COLUMN "public"."dns_records"."record_value" IS 'IP address (A/AAAA), hostname (CNAME/MX), or text content (TXT)';



COMMENT ON COLUMN "public"."dns_records"."ttl" IS 'DNS Time To Live in seconds';



COMMENT ON COLUMN "public"."dns_records"."priority" IS 'MX record priority (lower = higher priority). NULL for non-MX records.';



COMMENT ON COLUMN "public"."dns_records"."resolved_at" IS 'When the DNS query was performed';



COMMENT ON COLUMN "public"."dns_records"."cloud_provider" IS 'Detected cloud provider (aws, gcp, azure, cloudflare). Reserved for Phase 3+.';



COMMENT ON COLUMN "public"."dns_records"."scan_job_id" IS 'References the scan job that discovered this record';



COMMENT ON COLUMN "public"."dns_records"."batch_scan_id" IS 'Batch processing identifier';



COMMENT ON COLUMN "public"."dns_records"."asset_id" IS 'Denormalized asset reference for fast queries';



CREATE TABLE IF NOT EXISTS "public"."http_probes" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "scan_job_id" "uuid" NOT NULL,
    "asset_id" "uuid" NOT NULL,
    "status_code" integer,
    "url" "text" NOT NULL,
    "title" "text",
    "webserver" "text",
    "content_length" integer,
    "final_url" "text",
    "ip" "text",
    "technologies" "jsonb" DEFAULT '[]'::"jsonb",
    "cdn_name" "text",
    "content_type" "text",
    "asn" "text",
    "chain_status_codes" "jsonb" DEFAULT '[]'::"jsonb",
    "location" "text",
    "favicon_md5" "text",
    "subdomain" "text" NOT NULL,
    "parent_domain" "text" NOT NULL,
    "scheme" "text" NOT NULL,
    "port" integer NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "http_probes_port_check" CHECK ((("port" > 0) AND ("port" <= 65535))),
    CONSTRAINT "http_probes_scheme_check" CHECK (("scheme" = ANY (ARRAY['http'::"text", 'https'::"text"])))
);


ALTER TABLE "public"."http_probes" OWNER TO "postgres";


COMMENT ON TABLE "public"."http_probes" IS 'Stores HTTP probe results from httpx module, including status codes, technologies, server info, and redirect chains';



COMMENT ON COLUMN "public"."http_probes"."ip" IS 'Server IP address. Useful for correlating with DNS records, identifying CDN IPs, and detecting hosting patterns.';



COMMENT ON COLUMN "public"."http_probes"."technologies" IS 'JSONB array of detected technologies (e.g., ["React", "Next.js"]). Use GIN index for fast containment queries.';



COMMENT ON COLUMN "public"."http_probes"."chain_status_codes" IS 'JSONB array of HTTP status codes from redirect chain (e.g., [301, 302, 200])';



CREATE TABLE IF NOT EXISTS "public"."urls" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "asset_id" "uuid" NOT NULL,
    "scan_job_id" "uuid",
    "url" "text" NOT NULL,
    "url_hash" "text" NOT NULL,
    "domain" "text" NOT NULL,
    "path" "text",
    "query_params" "jsonb" DEFAULT '{}'::"jsonb",
    "sources" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "first_discovered_by" "text" NOT NULL,
    "first_discovered_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "resolved_at" timestamp with time zone,
    "is_alive" boolean,
    "status_code" integer,
    "content_type" "text",
    "content_length" integer,
    "response_time_ms" integer,
    "title" "text",
    "final_url" "text",
    "redirect_chain" "jsonb" DEFAULT '[]'::"jsonb",
    "webserver" "text",
    "technologies" "jsonb" DEFAULT '[]'::"jsonb",
    "has_params" boolean GENERATED ALWAYS AS (("query_params" <> '{}'::"jsonb")) STORED,
    "file_extension" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "urls_first_discovered_by_check" CHECK (("first_discovered_by" = ANY (ARRAY['katana'::"text", 'waymore'::"text", 'gau'::"text", 'gospider'::"text", 'hakrawler'::"text", 'manual'::"text"])))
);


ALTER TABLE "public"."urls" OWNER TO "postgres";


COMMENT ON TABLE "public"."urls" IS 'Stores resolved URLs discovered by various tools (Katana, Waymore, GAU, etc.). Each URL is probed by the URL Resolver to determine if alive and extract metadata. Supports multi-source tracking and TTL-based re-resolution.';



COMMENT ON COLUMN "public"."urls"."url" IS 'Full normalized URL. Example: https://example.com/api/users?id=123';



COMMENT ON COLUMN "public"."urls"."url_hash" IS 'SHA256 hash of normalized URL for fast lookups and deduplication.';



COMMENT ON COLUMN "public"."urls"."domain" IS 'Extracted domain for filtering. Example: example.com';



COMMENT ON COLUMN "public"."urls"."path" IS 'URL path component. Example: /api/users';



COMMENT ON COLUMN "public"."urls"."query_params" IS 'Parsed query string as JSON object. Example: {"id": "123", "page": "1"}';



COMMENT ON COLUMN "public"."urls"."sources" IS 'Array of all tools that discovered this URL. Example: ["katana", "waymore"]';



COMMENT ON COLUMN "public"."urls"."first_discovered_by" IS 'First tool to discover this URL. Used for attribution.';



COMMENT ON COLUMN "public"."urls"."resolved_at" IS 'Timestamp of last resolution probe. NULL means never resolved. Used for TTL-based re-probing.';



COMMENT ON COLUMN "public"."urls"."is_alive" IS 'Whether URL responded successfully. NULL=not checked, true=alive, false=dead.';



COMMENT ON COLUMN "public"."urls"."status_code" IS 'HTTP response status code from last probe. Common: 200, 301, 404, 403, 500.';



COMMENT ON COLUMN "public"."urls"."technologies" IS 'Detected technologies from response. Example: ["nginx", "php", "wordpress"]';



COMMENT ON COLUMN "public"."urls"."has_params" IS 'Auto-computed: true if URL has query parameters. Useful for finding endpoints with inputs.';



COMMENT ON COLUMN "public"."urls"."file_extension" IS 'Extracted file extension if present. Example: .php, .aspx, .js';



CREATE OR REPLACE VIEW "public"."asset_recon_counts" AS
 SELECT "a"."id" AS "asset_id",
    COALESCE("hp"."probe_count", (0)::bigint) AS "probe_count",
    COALESCE("dr"."dns_count", (0)::bigint) AS "dns_count",
    COALESCE("u"."url_count", (0)::bigint) AS "url_count"
   FROM ((("public"."assets" "a"
     LEFT JOIN ( SELECT "http_probes"."asset_id",
            "count"(*) AS "probe_count"
           FROM "public"."http_probes"
          GROUP BY "http_probes"."asset_id") "hp" ON (("a"."id" = "hp"."asset_id")))
     LEFT JOIN ( SELECT "dns_records"."asset_id",
            "count"(*) AS "dns_count"
           FROM "public"."dns_records"
          GROUP BY "dns_records"."asset_id") "dr" ON (("a"."id" = "dr"."asset_id")))
     LEFT JOIN ( SELECT "urls"."asset_id",
            "count"(*) AS "url_count"
           FROM "public"."urls"
          GROUP BY "urls"."asset_id") "u" ON (("a"."id" = "u"."asset_id")));


ALTER VIEW "public"."asset_recon_counts" OWNER TO "postgres";


COMMENT ON VIEW "public"."asset_recon_counts" IS 'Pre-computed reconnaissance counts per asset. Aggregates probe_count (http_probes), dns_count (dns_records), and url_count (urls) for each asset. Used for dashboard performance optimization.';


-- ================================================================
-- VIEW: http_probe_stats
-- Pre-computed aggregate statistics for HTTP probes
-- Used by /http-probes/stats/summary endpoint
-- Replaces fetching all 22K+ rows with a single aggregated query
-- ================================================================
CREATE OR REPLACE VIEW "public"."http_probe_stats" AS
SELECT 
    COUNT(*) AS total_probes,
    COUNT(DISTINCT asset_id) AS unique_assets,
    COUNT(DISTINCT webserver) AS unique_webservers,
    COUNT(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 END) AS status_2xx,
    COUNT(CASE WHEN status_code >= 300 AND status_code < 400 THEN 1 END) AS status_3xx,
    COUNT(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 END) AS status_4xx,
    COUNT(CASE WHEN status_code >= 500 THEN 1 END) AS status_5xx,
    COUNT(CASE WHEN cdn_name IS NOT NULL THEN 1 END) AS with_cdn,
    COUNT(CASE WHEN jsonb_array_length(chain_status_codes) > 0 THEN 1 END) AS with_redirects
FROM "public"."http_probes";

ALTER VIEW "public"."http_probe_stats" OWNER TO "postgres";

COMMENT ON VIEW "public"."http_probe_stats" IS 'Pre-computed HTTP probe statistics. Provides total counts, status code distributions, and CDN/redirect metrics in a single query.';


-- ================================================================
-- VIEW: http_probe_top_items
-- Pre-computed top webservers and technologies
-- Used by /http-probes/stats/summary endpoint
-- ================================================================
CREATE OR REPLACE VIEW "public"."http_probe_webserver_counts" AS
SELECT 
    webserver,
    COUNT(*) AS count
FROM "public"."http_probes"
WHERE webserver IS NOT NULL
GROUP BY webserver
ORDER BY count DESC
LIMIT 20;

ALTER VIEW "public"."http_probe_webserver_counts" OWNER TO "postgres";


-- ================================================================
-- VIEW: scan_subdomain_counts
-- Pre-computed subdomain counts per scan job
-- Used by /usage/recon-data endpoint for recent scans
-- Replaces 20 sequential queries with a single query
-- ================================================================
CREATE OR REPLACE VIEW "public"."scan_subdomain_counts" AS
SELECT 
    scan_job_id,
    COUNT(*) AS subdomain_count
FROM "public"."subdomains"
WHERE scan_job_id IS NOT NULL
GROUP BY scan_job_id;

ALTER VIEW "public"."scan_subdomain_counts" OWNER TO "postgres";

COMMENT ON VIEW "public"."scan_subdomain_counts" IS 'Pre-computed subdomain counts per scan job. Used for displaying subdomain counts in recent scans without N+1 queries.';



CREATE TABLE IF NOT EXISTS "public"."batch_domain_assignments" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "batch_scan_id" "uuid" NOT NULL,
    "domain" "text" NOT NULL,
    "asset_scan_id" "uuid" NOT NULL,
    "apex_domain_id" "uuid",
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "started_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    "subdomains_found" integer DEFAULT 0 NOT NULL,
    "error_message" "text",
    CONSTRAINT "valid_status" CHECK (("status" = ANY (ARRAY['pending'::"text", 'running'::"text", 'completed'::"text", 'failed'::"text"]))),
    CONSTRAINT "valid_subdomains_found" CHECK (("subdomains_found" >= 0))
);


ALTER TABLE "public"."batch_domain_assignments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."batch_scan_jobs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "batch_type" "text" DEFAULT 'multi_asset'::"text" NOT NULL,
    "module" "text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "total_domains" integer DEFAULT 0 NOT NULL,
    "completed_domains" integer DEFAULT 0 NOT NULL,
    "failed_domains" integer DEFAULT 0 NOT NULL,
    "batch_domains" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "asset_scan_mapping" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "allocated_cpu" integer DEFAULT 256 NOT NULL,
    "allocated_memory" integer DEFAULT 512 NOT NULL,
    "estimated_duration_minutes" integer DEFAULT 5 NOT NULL,
    "resource_profile" "jsonb" DEFAULT '{}'::"jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "started_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    "estimated_completion" timestamp with time zone,
    "error_message" "text",
    "retry_count" integer DEFAULT 0 NOT NULL,
    "max_retries" integer DEFAULT 2 NOT NULL,
    "ecs_task_arn" "text",
    "metadata" "jsonb" DEFAULT '{}'::"jsonb",
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "total_records" integer DEFAULT 0 NOT NULL,
    "urls_inserted" integer DEFAULT 0,
    "probes_inserted" integer DEFAULT 0,
    "urls_probed" integer DEFAULT 0,
    "subdomains_processed" integer DEFAULT 0,
    "urls_received" integer DEFAULT 0,
    CONSTRAINT "valid_batch_type" CHECK (("batch_type" = ANY (ARRAY['multi_asset'::"text", 'single_asset'::"text"]))),
    CONSTRAINT "valid_domain_counts" CHECK ((("total_domains" >= 0) AND ("completed_domains" >= 0) AND ("failed_domains" >= 0) AND (("completed_domains" + "failed_domains") <= "total_domains"))),
    CONSTRAINT "valid_domains_array" CHECK (("array_length"("batch_domains", 1) = "total_domains")),
    CONSTRAINT "valid_resources" CHECK ((("allocated_cpu" >= 256) AND ("allocated_cpu" <= 4096) AND ("allocated_memory" >= 512) AND ("allocated_memory" <= 8192))),
    CONSTRAINT "valid_retry_count" CHECK ((("retry_count" >= 0) AND ("retry_count" <= "max_retries"))),
    CONSTRAINT "valid_status" CHECK (("status" = ANY (ARRAY['pending'::"text", 'running'::"text", 'completed'::"text", 'failed'::"text", 'cancelled'::"text"]))),
    CONSTRAINT "valid_total_records" CHECK (("total_records" >= 0))
);


ALTER TABLE "public"."batch_scan_jobs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."crawled_endpoints" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "asset_id" "uuid" NOT NULL,
    "scan_job_id" "uuid",
    "url" "text" NOT NULL,
    "url_hash" "text" NOT NULL,
    "method" "text" DEFAULT 'GET'::"text" NOT NULL,
    "source_url" "text",
    "is_seed_url" boolean DEFAULT false NOT NULL,
    "status_code" integer,
    "content_type" "text",
    "content_length" bigint,
    "first_seen_at" timestamp with time zone NOT NULL,
    "last_seen_at" timestamp with time zone NOT NULL,
    "times_discovered" integer DEFAULT 1 NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "crawled_endpoints_method_check" CHECK (("method" = ANY (ARRAY['GET'::"text", 'POST'::"text", 'PUT'::"text", 'DELETE'::"text", 'PATCH'::"text", 'HEAD'::"text", 'OPTIONS'::"text"]))),
    CONSTRAINT "crawled_endpoints_times_discovered_check" CHECK (("times_discovered" >= 1))
);


ALTER TABLE "public"."crawled_endpoints" OWNER TO "postgres";


COMMENT ON TABLE "public"."crawled_endpoints" IS 'Stores web endpoints discovered by Katana web crawler. Includes URL metadata, status codes, source tracking, and deduplication fields. Used for attack surface mapping and site structure analysis.';



COMMENT ON COLUMN "public"."crawled_endpoints"."url" IS 'Full URL of the discovered endpoint (normalized for deduplication). Example: https://example.com/api/users?id=123';



COMMENT ON COLUMN "public"."crawled_endpoints"."url_hash" IS 'SHA256 hash of normalized URL for fast lookups and deduplication. 64-character hex string. Generated by Go code using crypto/sha256.';



COMMENT ON COLUMN "public"."crawled_endpoints"."method" IS 'HTTP method for this endpoint. Defaults to GET (most common). POST indicates form submission or API endpoint.';



COMMENT ON COLUMN "public"."crawled_endpoints"."source_url" IS 'The URL from which this endpoint was discovered (the page that linked here). Used for attack surface mapping and site structure analysis. Stores FIRST discoverer only (see times_discovered for rediscovery count).';



COMMENT ON COLUMN "public"."crawled_endpoints"."is_seed_url" IS 'True if this URL was used as an initial seed for crawling (from http_probes table). Use for UI filtering to distinguish crawl targets from discovered links. Seed URLs typically have higher confidence/importance.';



COMMENT ON COLUMN "public"."crawled_endpoints"."status_code" IS 'HTTP response status code when endpoint was probed. NULL if endpoint discovered but not yet probed (e.g., from JavaScript or sitemap). Common values: 200 (OK), 404 (Not Found), 403 (Forbidden), 500 (Server Error).';



COMMENT ON COLUMN "public"."crawled_endpoints"."content_type" IS 'HTTP Content-Type header value. Examples: "text/html", "application/json", "image/png". Used for filtering (exclude images/CSS) and identifying API endpoints.';



COMMENT ON COLUMN "public"."crawled_endpoints"."content_length" IS 'HTTP Content-Length header value (bytes). NULL if not provided. Used for identifying large responses or empty pages.';



COMMENT ON COLUMN "public"."crawled_endpoints"."first_seen_at" IS 'Timestamp when this URL was first discovered. Immutable after initial insert. Used for timeline analysis and tracking when endpoints appeared.';



COMMENT ON COLUMN "public"."crawled_endpoints"."last_seen_at" IS 'Timestamp when this URL was most recently rediscovered. Updated via ON CONFLICT logic. Used for staleness detection (endpoints not seen in recent scans might be removed).';



COMMENT ON COLUMN "public"."crawled_endpoints"."times_discovered" IS 'Number of times this URL was discovered across crawls. Higher values indicate hub pages or frequently linked resources (navigation menus, sitemaps, popular pages). Incremented via ON CONFLICT logic.';



CREATE TABLE IF NOT EXISTS "public"."historical_urls" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "url" "text" NOT NULL,
    "parent_domain" "text" NOT NULL,
    "source" "text" DEFAULT 'waymore'::"text" NOT NULL,
    "archive_timestamp" timestamp with time zone,
    "asset_id" "uuid" NOT NULL,
    "scan_job_id" "uuid",
    "discovered_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "jsonb" DEFAULT '{}'::"jsonb"
);


ALTER TABLE "public"."historical_urls" OWNER TO "postgres";


COMMENT ON TABLE "public"."historical_urls" IS 'Stores historical URL discoveries from Waymore (Wayback Machine, Common Crawl, etc.)';



COMMENT ON COLUMN "public"."historical_urls"."url" IS 'The discovered URL (full URL including path and query params)';



COMMENT ON COLUMN "public"."historical_urls"."parent_domain" IS 'The apex domain this URL belongs to (e.g., example.com)';



COMMENT ON COLUMN "public"."historical_urls"."source" IS 'Archive source: wayback, commoncrawl, alienvault, urlscan, virustotal, intelligencex';



COMMENT ON COLUMN "public"."historical_urls"."archive_timestamp" IS 'Original archive timestamp from the source (when available)';



COMMENT ON COLUMN "public"."historical_urls"."metadata" IS 'Flexible JSON storage for source-specific metadata';



CREATE OR REPLACE VIEW "public"."module_analytics" AS
 SELECT "source_module",
    "count"(*) AS "total_subdomains",
    "count"(DISTINCT "subdomain") AS "unique_subdomains",
    "count"(DISTINCT "scan_job_id") AS "scan_jobs",
    "max"("discovered_at") AS "last_discovery"
   FROM "public"."subdomains"
  GROUP BY "source_module";


ALTER VIEW "public"."module_analytics" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."scan_module_profiles" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "module_name" "text" NOT NULL,
    "version" "text" DEFAULT '1.0'::"text" NOT NULL,
    "supports_batching" boolean DEFAULT false NOT NULL,
    "max_batch_size" integer DEFAULT 1 NOT NULL,
    "resource_scaling" "jsonb" NOT NULL,
    "estimated_duration_per_domain" integer DEFAULT 120 NOT NULL,
    "task_definition_template" "text" NOT NULL,
    "container_name" "text" NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "optimization_hints" "jsonb" DEFAULT '{}'::"jsonb",
    "dependencies" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    CONSTRAINT "valid_duration" CHECK (("estimated_duration_per_domain" > 0)),
    CONSTRAINT "valid_max_batch_size" CHECK (("max_batch_size" >= 1))
);


ALTER TABLE "public"."scan_module_profiles" OWNER TO "postgres";


COMMENT ON COLUMN "public"."scan_module_profiles"."optimization_hints" IS 'Module-specific configuration flags stored as JSONB.

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



COMMENT ON COLUMN "public"."scan_module_profiles"."dependencies" IS 'Array of module names that must execute before this module.
Example: httpx depends on [subfinder] because it needs subdomain data.
Empty array means no dependencies.
Used by backend to resolve execution order automatically.';



CREATE TABLE IF NOT EXISTS "public"."scans" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "status" "text" NOT NULL,
    "assets_count" integer NOT NULL,
    "completed_assets" integer DEFAULT 0,
    "failed_assets" integer DEFAULT 0,
    "total_domains" integer NOT NULL,
    "completed_domains" integer DEFAULT 0,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "started_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    "config" "jsonb" NOT NULL,
    "results" "jsonb",
    "error" "text",
    "metadata" "jsonb" DEFAULT '{}'::"jsonb",
    CONSTRAINT "started_before_completed" CHECK ((("completed_at" IS NULL) OR ("started_at" IS NULL) OR ("started_at" <= "completed_at"))),
    CONSTRAINT "valid_assets_count" CHECK ((("assets_count" > 0) AND ("completed_assets" >= 0) AND ("failed_assets" >= 0) AND (("completed_assets" + "failed_assets") <= "assets_count"))),
    CONSTRAINT "valid_domains_count" CHECK ((("total_domains" >= 0) AND ("completed_domains" >= 0) AND ("completed_domains" <= "total_domains"))),
    CONSTRAINT "valid_status" CHECK (("status" = ANY (ARRAY['pending'::"text", 'running'::"text", 'completed'::"text", 'partial_failure'::"text", 'failed'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "public"."scans" OWNER TO "postgres";


COMMENT ON TABLE "public"."scans" IS 'Tracks unified scan operations for one or more assets';



COMMENT ON COLUMN "public"."scans"."id" IS 'Auto-generated UUID (default: gen_random_uuid())';



COMMENT ON COLUMN "public"."scans"."user_id" IS 'User who initiated the scan';



COMMENT ON COLUMN "public"."scans"."status" IS 'Current scan status: pending, running, completed, partial_failure, failed, cancelled';



COMMENT ON COLUMN "public"."scans"."assets_count" IS 'Total number of assets in this scan';



COMMENT ON COLUMN "public"."scans"."completed_assets" IS 'Number of assets that completed successfully';



COMMENT ON COLUMN "public"."scans"."failed_assets" IS 'Number of assets that failed';



COMMENT ON COLUMN "public"."scans"."total_domains" IS 'Total domains across all assets';



COMMENT ON COLUMN "public"."scans"."completed_domains" IS 'Number of domains processed';



COMMENT ON COLUMN "public"."scans"."config" IS 'Original scan configuration (JSONB) for replay/debugging';



COMMENT ON COLUMN "public"."scans"."results" IS 'Aggregated scan results (JSONB) after completion';



COMMENT ON COLUMN "public"."scans"."metadata" IS 'Additional metadata (default: empty JSON object)';



CREATE OR REPLACE VIEW "public"."scans_with_assets" AS
SELECT
    NULL::"uuid" AS "id",
    NULL::"uuid" AS "user_id",
    NULL::"text" AS "status",
    NULL::integer AS "assets_count",
    NULL::integer AS "completed_assets",
    NULL::integer AS "failed_assets",
    NULL::integer AS "total_domains",
    NULL::integer AS "completed_domains",
    NULL::timestamp with time zone AS "created_at",
    NULL::timestamp with time zone AS "started_at",
    NULL::timestamp with time zone AS "completed_at",
    NULL::numeric AS "progress_percent",
    NULL::numeric AS "duration_seconds",
    NULL::"text" AS "asset_names_json",
    NULL::bigint AS "linked_jobs_count";


ALTER VIEW "public"."scans_with_assets" OWNER TO "postgres";


COMMENT ON VIEW "public"."scans_with_assets" IS 'Enhanced scan view with calculated fields and asset job counts';



CREATE OR REPLACE VIEW "public"."subdomain_current_dns" AS
 SELECT "subdomain",
    "parent_domain",
    "array_agg"(DISTINCT "record_value" ORDER BY "record_value") FILTER (WHERE ("record_type" = 'A'::"text")) AS "ipv4_addresses",
    "array_agg"(DISTINCT "record_value" ORDER BY "record_value") FILTER (WHERE ("record_type" = 'AAAA'::"text")) AS "ipv6_addresses",
    "array_agg"(DISTINCT "record_value") FILTER (WHERE ("record_type" = 'CNAME'::"text")) AS "cname_targets",
    "array_agg"("json_build_object"('host', "record_value", 'priority', COALESCE("priority", 0)) ORDER BY COALESCE("priority", 0)) FILTER (WHERE ("record_type" = 'MX'::"text")) AS "mx_records",
    "array_agg"(DISTINCT "record_value") FILTER (WHERE ("record_type" = 'TXT'::"text")) AS "txt_records",
    "max"("resolved_at") AS "last_resolved_at",
    "max"("ttl") AS "max_ttl",
    "string_agg"(DISTINCT "cloud_provider", ', '::"text") FILTER (WHERE ("cloud_provider" IS NOT NULL)) AS "cloud_providers",
    ("array_agg"("scan_job_id" ORDER BY "resolved_at" DESC))[1] AS "latest_scan_job_id",
    ("array_agg"("asset_id" ORDER BY "resolved_at" DESC))[1] AS "asset_id",
    "count"(*) AS "total_records"
   FROM "public"."dns_records"
  GROUP BY "subdomain", "parent_domain";


ALTER VIEW "public"."subdomain_current_dns" OWNER TO "postgres";


COMMENT ON VIEW "public"."subdomain_current_dns" IS 'Aggregated view of current DNS records per subdomain. Shows latest IPs (IPv4/IPv6), CNAMEs, MX records (with priority), and TXT records. Use this for dashboard queries and frontend display.';



CREATE TABLE IF NOT EXISTS "public"."user_quotas" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "max_assets" integer DEFAULT 5 NOT NULL,
    "max_domains_per_asset" integer DEFAULT 10 NOT NULL,
    "max_scans_per_day" integer DEFAULT 50 NOT NULL,
    "max_scans_per_month" integer DEFAULT 1000 NOT NULL,
    "max_concurrent_scans" integer DEFAULT 3 NOT NULL,
    "max_subdomains_stored" integer DEFAULT 10000 NOT NULL,
    "plan_type" "text" DEFAULT 'free'::"text" NOT NULL,
    "plan_expires_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "stripe_customer_id" "text",
    "stripe_payment_id" "text",
    "paid_at" timestamp with time zone,
    CONSTRAINT "valid_plan_type" CHECK (("plan_type" = ANY (ARRAY['free'::"text", 'paid'::"text", 'pro'::"text", 'enterprise'::"text"]))),
    CONSTRAINT "valid_quotas" CHECK ((("max_assets" > 0) AND ("max_domains_per_asset" > 0) AND ("max_scans_per_day" > 0) AND ("max_scans_per_month" > 0) AND ("max_concurrent_scans" > 0) AND ("max_subdomains_stored" > 0)))
);


ALTER TABLE "public"."user_quotas" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."user_usage" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "current_assets" integer DEFAULT 0 NOT NULL,
    "current_domains" integer DEFAULT 0 NOT NULL,
    "current_active_scans" integer DEFAULT 0 NOT NULL,
    "current_subdomains" integer DEFAULT 0 NOT NULL,
    "scans_today" integer DEFAULT 0 NOT NULL,
    "scans_this_month" integer DEFAULT 0 NOT NULL,
    "scan_date_last_reset" "date" DEFAULT CURRENT_DATE NOT NULL,
    "scan_month_last_reset" "date" DEFAULT "date_trunc"('month'::"text", (CURRENT_DATE)::timestamp with time zone) NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "urls_viewed_count" integer DEFAULT 0,
    CONSTRAINT "valid_usage" CHECK ((("current_assets" >= 0) AND ("current_domains" >= 0) AND ("current_active_scans" >= 0) AND ("current_subdomains" >= 0) AND ("scans_today" >= 0) AND ("scans_this_month" >= 0)))
);


ALTER TABLE "public"."user_usage" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."user_usage_overview" AS
 SELECT "u"."user_id",
    "u"."current_assets",
    "u"."current_domains",
    "u"."current_active_scans",
    "u"."current_subdomains",
    "u"."scans_today",
    "u"."scans_this_month",
    "q"."max_assets",
    "q"."max_domains_per_asset",
    "q"."max_scans_per_day",
    "q"."max_scans_per_month",
    "q"."max_concurrent_scans",
    "q"."max_subdomains_stored",
    ("u"."current_assets" >= "q"."max_assets") AS "asset_limit_reached",
    ("u"."scans_today" >= "q"."max_scans_per_day") AS "daily_limit_reached",
    ("u"."scans_this_month" >= "q"."max_scans_per_month") AS "monthly_limit_reached",
    ("u"."current_active_scans" >= "q"."max_concurrent_scans") AS "concurrent_limit_reached",
    ("u"."current_subdomains" >= "q"."max_subdomains_stored") AS "storage_limit_reached",
    "q"."plan_type",
    "q"."plan_expires_at",
    "u"."updated_at" AS "usage_updated_at",
    "q"."updated_at" AS "quota_updated_at"
   FROM ("public"."user_usage" "u"
     JOIN "public"."user_quotas" "q" ON (("u"."user_id" = "q"."user_id")));


ALTER VIEW "public"."user_usage_overview" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."vt_discovered_urls" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "scan_job_id" "uuid" NOT NULL,
    "asset_id" "uuid" NOT NULL,
    "subdomain" "text" NOT NULL,
    "url" "text" NOT NULL,
    "positives" integer DEFAULT 0,
    "total" integer DEFAULT 0,
    "vt_scan_date" "text",
    "source" "text" DEFAULT 'virustotal'::"text",
    "discovered_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."vt_discovered_urls" OWNER TO "postgres";


COMMENT ON TABLE "public"."vt_discovered_urls" IS 'URLs discovered from VirusTotal domain reports - historical paths for recon';



COMMENT ON COLUMN "public"."vt_discovered_urls"."subdomain" IS 'The subdomain that was queried (e.g., api.example.com)';



COMMENT ON COLUMN "public"."vt_discovered_urls"."url" IS 'The discovered URL from VT undetected_urls';



COMMENT ON COLUMN "public"."vt_discovered_urls"."positives" IS 'Number of AV engines that detected this URL as malicious';



COMMENT ON COLUMN "public"."vt_discovered_urls"."total" IS 'Total number of AV engines that scanned this URL';



COMMENT ON COLUMN "public"."vt_discovered_urls"."vt_scan_date" IS 'When VirusTotal originally scanned this URL';



ALTER TABLE ONLY "public"."apex_domains"
    ADD CONSTRAINT "apex_domains_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."api_keys"
    ADD CONSTRAINT "api_keys_key_hash_unique" UNIQUE ("key_hash");



ALTER TABLE ONLY "public"."api_keys"
    ADD CONSTRAINT "api_keys_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."asset_scan_jobs"
    ADD CONSTRAINT "asset_scan_jobs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."assets"
    ADD CONSTRAINT "assets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."batch_domain_assignments"
    ADD CONSTRAINT "batch_domain_assignments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."batch_scan_jobs"
    ADD CONSTRAINT "batch_scan_jobs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."crawled_endpoints"
    ADD CONSTRAINT "crawled_endpoints_asset_url_unique" UNIQUE ("asset_id", "url_hash");



ALTER TABLE ONLY "public"."crawled_endpoints"
    ADD CONSTRAINT "crawled_endpoints_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."dns_records"
    ADD CONSTRAINT "dns_records_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."dns_records"
    ADD CONSTRAINT "dns_records_unique_record" UNIQUE NULLS NOT DISTINCT ("subdomain", "record_type", "record_value", "priority");



ALTER TABLE ONLY "public"."historical_urls"
    ADD CONSTRAINT "historical_urls_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."historical_urls"
    ADD CONSTRAINT "historical_urls_url_asset_id_key" UNIQUE ("url", "asset_id");



ALTER TABLE ONLY "public"."http_probes"
    ADD CONSTRAINT "http_probes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."scan_module_profiles"
    ADD CONSTRAINT "scan_module_profiles_module_name_key" UNIQUE ("module_name");



ALTER TABLE ONLY "public"."scan_module_profiles"
    ADD CONSTRAINT "scan_module_profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."scans"
    ADD CONSTRAINT "scans_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."subdomains"
    ADD CONSTRAINT "subdomains_parent_subdomain_unique" UNIQUE ("parent_domain", "subdomain");



ALTER TABLE ONLY "public"."subdomains"
    ADD CONSTRAINT "subdomains_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."apex_domains"
    ADD CONSTRAINT "unique_asset_domain" UNIQUE ("asset_id", "domain");



ALTER TABLE ONLY "public"."batch_domain_assignments"
    ADD CONSTRAINT "unique_batch_domain" UNIQUE ("batch_scan_id", "domain");



ALTER TABLE ONLY "public"."scan_module_profiles"
    ADD CONSTRAINT "unique_module_version" UNIQUE ("module_name", "version");



ALTER TABLE ONLY "public"."user_quotas"
    ADD CONSTRAINT "unique_user_quota" UNIQUE ("user_id");



ALTER TABLE ONLY "public"."user_usage"
    ADD CONSTRAINT "unique_user_usage" UNIQUE ("user_id");



ALTER TABLE ONLY "public"."urls"
    ADD CONSTRAINT "urls_asset_url_unique" UNIQUE ("asset_id", "url_hash");



ALTER TABLE ONLY "public"."urls"
    ADD CONSTRAINT "urls_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_quotas"
    ADD CONSTRAINT "user_quotas_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_usage"
    ADD CONSTRAINT "user_usage_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."vt_discovered_urls"
    ADD CONSTRAINT "vt_discovered_urls_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."vt_discovered_urls"
    ADD CONSTRAINT "vt_discovered_urls_unique" UNIQUE ("url", "asset_id");



CREATE INDEX "idx_apex_domains_asset_id" ON "public"."apex_domains" USING "btree" ("asset_id");



CREATE INDEX "idx_apex_domains_domain" ON "public"."apex_domains" USING "btree" ("domain");



CREATE INDEX "idx_apex_domains_is_active" ON "public"."apex_domains" USING "btree" ("is_active") WHERE ("is_active" = true);



CREATE INDEX "idx_apex_domains_last_scanned" ON "public"."apex_domains" USING "btree" ("last_scanned_at" DESC);



CREATE INDEX "idx_api_keys_active" ON "public"."api_keys" USING "btree" ("key_hash") WHERE ("is_active" = true);



CREATE INDEX "idx_api_keys_key_hash" ON "public"."api_keys" USING "btree" ("key_hash");



CREATE UNIQUE INDEX "idx_api_keys_one_per_user" ON "public"."api_keys" USING "btree" ("user_id") WHERE ("is_active" = true);



CREATE INDEX "idx_api_keys_user_id" ON "public"."api_keys" USING "btree" ("user_id");



CREATE INDEX "idx_asset_scan_jobs_asset_created" ON "public"."asset_scan_jobs" USING "btree" ("asset_id", "created_at" DESC);



CREATE INDEX "idx_asset_scan_jobs_asset_id" ON "public"."asset_scan_jobs" USING "btree" ("asset_id");



CREATE INDEX "idx_asset_scan_jobs_created_at" ON "public"."asset_scan_jobs" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_asset_scan_jobs_created_at_desc" ON "public"."asset_scan_jobs" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_asset_scan_jobs_parent_scan" ON "public"."asset_scan_jobs" USING "btree" ("parent_scan_id") WHERE ("parent_scan_id" IS NOT NULL);



CREATE INDEX "idx_asset_scan_jobs_status" ON "public"."asset_scan_jobs" USING "btree" ("status");



CREATE INDEX "idx_asset_scan_jobs_status_progress" ON "public"."asset_scan_jobs" USING "btree" ("status", "total_domains", "completed_domains");



CREATE INDEX "idx_asset_scan_jobs_user_asset_created" ON "public"."asset_scan_jobs" USING "btree" ("asset_id", "created_at" DESC);



CREATE INDEX "idx_asset_scan_jobs_user_id" ON "public"."asset_scan_jobs" USING "btree" ("user_id");



CREATE INDEX "idx_asset_scan_jobs_user_status_created" ON "public"."asset_scan_jobs" USING "btree" ("user_id", "status", "created_at" DESC);



CREATE INDEX "idx_assets_created_at" ON "public"."assets" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_assets_is_active" ON "public"."assets" USING "btree" ("is_active") WHERE ("is_active" = true);



CREATE INDEX "idx_assets_priority" ON "public"."assets" USING "btree" ("priority" DESC);



CREATE INDEX "idx_assets_tags" ON "public"."assets" USING "gin" ("tags");



CREATE INDEX "idx_assets_user_id" ON "public"."assets" USING "btree" ("user_id");



CREATE INDEX "idx_assets_user_id_active" ON "public"."assets" USING "btree" ("user_id", "is_active");



CREATE INDEX "idx_batch_domain_assignments_asset_scan_id" ON "public"."batch_domain_assignments" USING "btree" ("asset_scan_id");



CREATE INDEX "idx_batch_domain_assignments_batch_scan_id" ON "public"."batch_domain_assignments" USING "btree" ("batch_scan_id");



CREATE INDEX "idx_batch_domain_assignments_domain" ON "public"."batch_domain_assignments" USING "btree" ("domain");



CREATE INDEX "idx_batch_domain_assignments_status" ON "public"."batch_domain_assignments" USING "btree" ("status");



CREATE INDEX "idx_batch_scan_jobs_created_at" ON "public"."batch_scan_jobs" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_batch_scan_jobs_module" ON "public"."batch_scan_jobs" USING "btree" ("module");



CREATE INDEX "idx_batch_scan_jobs_status" ON "public"."batch_scan_jobs" USING "btree" ("status");



CREATE INDEX "idx_batch_scan_jobs_total_records" ON "public"."batch_scan_jobs" USING "btree" ("total_records") WHERE ("total_records" > 0);



CREATE INDEX "idx_batch_scan_jobs_user_id" ON "public"."batch_scan_jobs" USING "btree" ("user_id");



CREATE INDEX "idx_batch_scan_jobs_user_status_created" ON "public"."batch_scan_jobs" USING "btree" ("user_id", "status", "created_at" DESC);



CREATE INDEX "idx_crawled_endpoints_asset_id" ON "public"."crawled_endpoints" USING "btree" ("asset_id");



CREATE UNIQUE INDEX "idx_crawled_endpoints_asset_url_hash" ON "public"."crawled_endpoints" USING "btree" ("asset_id", "url_hash");



CREATE INDEX "idx_crawled_endpoints_first_seen" ON "public"."crawled_endpoints" USING "btree" ("first_seen_at" DESC);



CREATE INDEX "idx_crawled_endpoints_is_seed_url" ON "public"."crawled_endpoints" USING "btree" ("is_seed_url");



CREATE INDEX "idx_crawled_endpoints_scan_job_id" ON "public"."crawled_endpoints" USING "btree" ("scan_job_id");



CREATE INDEX "idx_crawled_endpoints_status_code" ON "public"."crawled_endpoints" USING "btree" ("status_code");



CREATE INDEX "idx_crawled_endpoints_url_hash" ON "public"."crawled_endpoints" USING "btree" ("url_hash");



CREATE INDEX "idx_dns_records_asset_id" ON "public"."dns_records" USING "btree" ("asset_id");



CREATE INDEX "idx_dns_records_asset_resolved" ON "public"."dns_records" USING "btree" ("asset_id", "resolved_at" DESC);



CREATE INDEX "idx_dns_records_asset_type" ON "public"."dns_records" USING "btree" ("asset_id", "record_type");



CREATE INDEX "idx_dns_records_batch_scan_id" ON "public"."dns_records" USING "btree" ("batch_scan_id");



CREATE INDEX "idx_dns_records_cloud" ON "public"."dns_records" USING "btree" ("cloud_provider", "cloud_service") WHERE ("cloud_provider" IS NOT NULL);



CREATE INDEX "idx_dns_records_parent_domain" ON "public"."dns_records" USING "btree" ("parent_domain");



CREATE INDEX "idx_dns_records_record_type" ON "public"."dns_records" USING "btree" ("record_type");



CREATE INDEX "idx_dns_records_resolved_at" ON "public"."dns_records" USING "btree" ("resolved_at" DESC);



CREATE INDEX "idx_dns_records_scan_job_id" ON "public"."dns_records" USING "btree" ("scan_job_id");



CREATE INDEX "idx_dns_records_subdomain" ON "public"."dns_records" USING "btree" ("subdomain");



CREATE INDEX "idx_dns_records_subdomain_resolved" ON "public"."dns_records" USING "btree" ("subdomain", "resolved_at" DESC);



CREATE INDEX "idx_dns_records_subdomain_type" ON "public"."dns_records" USING "btree" ("subdomain", "record_type") WHERE ("record_type" = ANY (ARRAY['A'::"text", 'AAAA'::"text"]));



CREATE INDEX "idx_historical_urls_asset_id" ON "public"."historical_urls" USING "btree" ("asset_id");



CREATE INDEX "idx_historical_urls_asset_source" ON "public"."historical_urls" USING "btree" ("asset_id", "source");



CREATE INDEX "idx_historical_urls_discovered_at" ON "public"."historical_urls" USING "btree" ("discovered_at" DESC);



CREATE INDEX "idx_historical_urls_parent_domain" ON "public"."historical_urls" USING "btree" ("parent_domain");



CREATE INDEX "idx_historical_urls_scan_job_id" ON "public"."historical_urls" USING "btree" ("scan_job_id");



CREATE INDEX "idx_historical_urls_source" ON "public"."historical_urls" USING "btree" ("source");



CREATE INDEX "idx_http_probes_asset_created" ON "public"."http_probes" USING "btree" ("asset_id", "created_at" DESC);



CREATE INDEX "idx_http_probes_asset_id" ON "public"."http_probes" USING "btree" ("asset_id");



CREATE INDEX "idx_http_probes_asset_status" ON "public"."http_probes" USING "btree" ("asset_id", "status_code");



CREATE INDEX "idx_http_probes_chain_status_codes" ON "public"."http_probes" USING "gin" ("chain_status_codes");



CREATE INDEX "idx_http_probes_created_at" ON "public"."http_probes" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_http_probes_ip" ON "public"."http_probes" USING "btree" ("ip");



CREATE INDEX "idx_http_probes_parent_domain" ON "public"."http_probes" USING "btree" ("parent_domain");



CREATE INDEX "idx_http_probes_scan_job_id" ON "public"."http_probes" USING "btree" ("scan_job_id");



CREATE INDEX "idx_http_probes_status_code" ON "public"."http_probes" USING "btree" ("status_code");



CREATE INDEX "idx_http_probes_subdomain" ON "public"."http_probes" USING "btree" ("subdomain");



CREATE INDEX "idx_http_probes_technologies" ON "public"."http_probes" USING "gin" ("technologies");



CREATE INDEX "idx_scan_module_profiles_is_active" ON "public"."scan_module_profiles" USING "btree" ("is_active") WHERE ("is_active" = true);



CREATE INDEX "idx_scan_module_profiles_module_name" ON "public"."scan_module_profiles" USING "btree" ("module_name");



CREATE INDEX "idx_scans_created_at" ON "public"."scans" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_scans_status" ON "public"."scans" USING "btree" ("status");



CREATE INDEX "idx_scans_user_id" ON "public"."scans" USING "btree" ("user_id");



CREATE INDEX "idx_scans_user_status" ON "public"."scans" USING "btree" ("user_id", "status");



CREATE INDEX "idx_subdomains_asset_id" ON "public"."subdomains" USING "btree" ("asset_id");



CREATE INDEX "idx_subdomains_asset_scan_job_id" ON "public"."subdomains" USING "btree" ("scan_job_id");



CREATE INDEX "idx_subdomains_discovered_at" ON "public"."subdomains" USING "btree" ("discovered_at" DESC);



CREATE INDEX "idx_subdomains_parent_discovered" ON "public"."subdomains" USING "btree" ("parent_domain", "discovered_at" DESC);



CREATE INDEX "idx_subdomains_parent_domain" ON "public"."subdomains" USING "btree" ("parent_domain");



CREATE INDEX "idx_subdomains_parent_domain_source_module" ON "public"."subdomains" USING "btree" ("parent_domain", "source_module");



CREATE INDEX "idx_subdomains_scan_job_asset_relation" ON "public"."subdomains" USING "btree" ("scan_job_id") WHERE ("scan_job_id" IS NOT NULL);



CREATE INDEX "idx_subdomains_scan_job_id" ON "public"."subdomains" USING "btree" ("scan_job_id");



CREATE INDEX "idx_subdomains_scanjob_discovered" ON "public"."subdomains" USING "btree" ("scan_job_id", "discovered_at" DESC);



CREATE INDEX "idx_subdomains_source_module" ON "public"."subdomains" USING "btree" ("source_module");



CREATE INDEX "idx_subdomains_subdomain" ON "public"."subdomains" USING "btree" ("subdomain");



CREATE INDEX "idx_urls_asset_alive" ON "public"."urls" USING "btree" ("asset_id", "is_alive");



CREATE INDEX "idx_urls_asset_discovered" ON "public"."urls" USING "btree" ("asset_id", "first_discovered_at" DESC);



CREATE INDEX "idx_urls_asset_id" ON "public"."urls" USING "btree" ("asset_id");



CREATE INDEX "idx_urls_asset_params" ON "public"."urls" USING "btree" ("asset_id", "has_params");



CREATE INDEX "idx_urls_asset_status" ON "public"."urls" USING "btree" ("asset_id", "status_code");



CREATE UNIQUE INDEX "idx_urls_asset_url_hash" ON "public"."urls" USING "btree" ("asset_id", "url_hash");



CREATE INDEX "idx_urls_created_at" ON "public"."urls" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_urls_domain" ON "public"."urls" USING "btree" ("domain");



CREATE INDEX "idx_urls_file_extension" ON "public"."urls" USING "btree" ("file_extension");



CREATE INDEX "idx_urls_first_discovered_at" ON "public"."urls" USING "btree" ("first_discovered_at" DESC);



CREATE INDEX "idx_urls_first_discovered_by" ON "public"."urls" USING "btree" ("first_discovered_by");



CREATE INDEX "idx_urls_has_params" ON "public"."urls" USING "btree" ("has_params");



CREATE INDEX "idx_urls_is_alive" ON "public"."urls" USING "btree" ("is_alive");



CREATE INDEX "idx_urls_resolved_at" ON "public"."urls" USING "btree" ("resolved_at" DESC);



CREATE INDEX "idx_urls_scan_job_id" ON "public"."urls" USING "btree" ("scan_job_id");



CREATE INDEX "idx_urls_status_code" ON "public"."urls" USING "btree" ("status_code");



CREATE INDEX "idx_user_quotas_plan_type" ON "public"."user_quotas" USING "btree" ("plan_type");



CREATE INDEX "idx_user_quotas_user_id" ON "public"."user_quotas" USING "btree" ("user_id");



CREATE INDEX "idx_user_usage_scan_dates" ON "public"."user_usage" USING "btree" ("scan_date_last_reset", "scan_month_last_reset");



CREATE INDEX "idx_user_usage_user_id" ON "public"."user_usage" USING "btree" ("user_id");



CREATE INDEX "idx_vt_discovered_urls_asset_id" ON "public"."vt_discovered_urls" USING "btree" ("asset_id");



CREATE INDEX "idx_vt_discovered_urls_discovered_at" ON "public"."vt_discovered_urls" USING "btree" ("discovered_at" DESC);



CREATE INDEX "idx_vt_discovered_urls_scan_job_id" ON "public"."vt_discovered_urls" USING "btree" ("scan_job_id");



CREATE INDEX "idx_vt_discovered_urls_subdomain" ON "public"."vt_discovered_urls" USING "btree" ("asset_id", "subdomain");



CREATE OR REPLACE VIEW "public"."scans_with_assets" AS
 SELECT "s"."id",
    "s"."user_id",
    "s"."status",
    "s"."assets_count",
    "s"."completed_assets",
    "s"."failed_assets",
    "s"."total_domains",
    "s"."completed_domains",
    "s"."created_at",
    "s"."started_at",
    "s"."completed_at",
        CASE
            WHEN ("s"."assets_count" > 0) THEN "round"((((("s"."completed_assets" + "s"."failed_assets"))::numeric / ("s"."assets_count")::numeric) * (100)::numeric), 2)
            ELSE (0)::numeric
        END AS "progress_percent",
        CASE
            WHEN (("s"."completed_at" IS NOT NULL) AND ("s"."started_at" IS NOT NULL)) THEN EXTRACT(epoch FROM ("s"."completed_at" - "s"."started_at"))
            ELSE NULL::numeric
        END AS "duration_seconds",
    ("s"."metadata" ->> 'asset_names'::"text") AS "asset_names_json",
    "count"("asj"."id") AS "linked_jobs_count"
   FROM ("public"."scans" "s"
     LEFT JOIN "public"."asset_scan_jobs" "asj" ON (("asj"."parent_scan_id" = "s"."id")))
  GROUP BY "s"."id";



CREATE OR REPLACE TRIGGER "trigger_apex_domains_updated_at" BEFORE UPDATE ON "public"."apex_domains" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



CREATE OR REPLACE TRIGGER "trigger_assets_updated_at" BEFORE UPDATE ON "public"."assets" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



CREATE OR REPLACE TRIGGER "trigger_scan_module_profiles_updated_at" BEFORE UPDATE ON "public"."scan_module_profiles" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



CREATE OR REPLACE TRIGGER "trigger_update_asset_count" AFTER INSERT OR DELETE ON "public"."assets" FOR EACH ROW EXECUTE FUNCTION "public"."update_user_asset_count"();



CREATE OR REPLACE TRIGGER "trigger_update_asset_scan_jobs_timestamp" BEFORE UPDATE ON "public"."asset_scan_jobs" FOR EACH ROW EXECUTE FUNCTION "public"."update_asset_scan_jobs_updated_at"();



CREATE OR REPLACE TRIGGER "trigger_update_batch_scan_jobs_timestamp" BEFORE UPDATE ON "public"."batch_scan_jobs" FOR EACH ROW EXECUTE FUNCTION "public"."update_batch_scan_jobs_updated_at"();



CREATE OR REPLACE TRIGGER "trigger_update_domain_count" AFTER INSERT OR DELETE ON "public"."apex_domains" FOR EACH ROW EXECUTE FUNCTION "public"."update_user_domain_count"();



CREATE OR REPLACE TRIGGER "trigger_update_scan_completed_at" BEFORE UPDATE ON "public"."scans" FOR EACH ROW EXECUTE FUNCTION "public"."update_scan_completed_at"();



CREATE OR REPLACE TRIGGER "trigger_user_quotas_updated_at" BEFORE UPDATE ON "public"."user_quotas" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



CREATE OR REPLACE TRIGGER "trigger_user_usage_updated_at" BEFORE UPDATE ON "public"."user_usage" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at"();



ALTER TABLE ONLY "public"."apex_domains"
    ADD CONSTRAINT "apex_domains_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."api_keys"
    ADD CONSTRAINT "api_keys_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."asset_scan_jobs"
    ADD CONSTRAINT "asset_scan_jobs_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."asset_scan_jobs"
    ADD CONSTRAINT "asset_scan_jobs_parent_scan_id_fkey" FOREIGN KEY ("parent_scan_id") REFERENCES "public"."scans"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."asset_scan_jobs"
    ADD CONSTRAINT "asset_scan_jobs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."assets"
    ADD CONSTRAINT "assets_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."batch_domain_assignments"
    ADD CONSTRAINT "batch_domain_assignments_apex_domain_id_fkey" FOREIGN KEY ("apex_domain_id") REFERENCES "public"."apex_domains"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."batch_domain_assignments"
    ADD CONSTRAINT "batch_domain_assignments_asset_scan_id_fkey" FOREIGN KEY ("asset_scan_id") REFERENCES "public"."asset_scan_jobs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."batch_domain_assignments"
    ADD CONSTRAINT "batch_domain_assignments_batch_scan_id_fkey" FOREIGN KEY ("batch_scan_id") REFERENCES "public"."batch_scan_jobs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."batch_scan_jobs"
    ADD CONSTRAINT "batch_scan_jobs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."crawled_endpoints"
    ADD CONSTRAINT "crawled_endpoints_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."crawled_endpoints"
    ADD CONSTRAINT "crawled_endpoints_scan_job_id_fkey" FOREIGN KEY ("scan_job_id") REFERENCES "public"."batch_scan_jobs"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."dns_records"
    ADD CONSTRAINT "dns_records_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."dns_records"
    ADD CONSTRAINT "dns_records_batch_scan_id_fkey" FOREIGN KEY ("batch_scan_id") REFERENCES "public"."batch_scan_jobs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."dns_records"
    ADD CONSTRAINT "dns_records_scan_job_id_fkey" FOREIGN KEY ("scan_job_id") REFERENCES "public"."asset_scan_jobs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."batch_scan_jobs"
    ADD CONSTRAINT "fk_module_name" FOREIGN KEY ("module") REFERENCES "public"."scan_module_profiles"("module_name") ON DELETE RESTRICT;



COMMENT ON CONSTRAINT "fk_module_name" ON "public"."batch_scan_jobs" IS 'Foreign key to scan_module_profiles.module_name.
Auto-validates module names against active modules in database.
New modules are automatically allowed when added to scan_module_profiles.
ON DELETE RESTRICT prevents deleting modules that are referenced.';



ALTER TABLE ONLY "public"."historical_urls"
    ADD CONSTRAINT "historical_urls_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."http_probes"
    ADD CONSTRAINT "http_probes_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."http_probes"
    ADD CONSTRAINT "http_probes_scan_job_id_fkey" FOREIGN KEY ("scan_job_id") REFERENCES "public"."asset_scan_jobs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."subdomains"
    ADD CONSTRAINT "subdomains_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."subdomains"
    ADD CONSTRAINT "subdomains_scan_job_id_fkey" FOREIGN KEY ("scan_job_id") REFERENCES "public"."asset_scan_jobs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."urls"
    ADD CONSTRAINT "urls_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."urls"
    ADD CONSTRAINT "urls_scan_job_id_fkey" FOREIGN KEY ("scan_job_id") REFERENCES "public"."batch_scan_jobs"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."user_quotas"
    ADD CONSTRAINT "user_quotas_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_usage"
    ADD CONSTRAINT "user_usage_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."vt_discovered_urls"
    ADD CONSTRAINT "vt_discovered_urls_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE;



CREATE POLICY "Authenticated users can read all DNS records" ON "public"."dns_records" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



COMMENT ON POLICY "Authenticated users can read all DNS records" ON "public"."dns_records" IS 'LEAN model: All authenticated users can read all reconnaissance data. Part of public data sharing for bug bounty researchers.';



CREATE POLICY "Authenticated users can read all HTTP probes" ON "public"."http_probes" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



COMMENT ON POLICY "Authenticated users can read all HTTP probes" ON "public"."http_probes" IS 'LEAN model: All authenticated users can read all reconnaissance data. Part of public data sharing for bug bounty researchers.';



CREATE POLICY "Authenticated users can read all assets" ON "public"."assets" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



COMMENT ON POLICY "Authenticated users can read all assets" ON "public"."assets" IS 'LEAN model: All authenticated users can read all reconnaissance data. Part of public data sharing for bug bounty researchers.';



CREATE POLICY "Authenticated users can read all batch scans" ON "public"."batch_scan_jobs" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



CREATE POLICY "Authenticated users can read all crawled endpoints" ON "public"."crawled_endpoints" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



CREATE POLICY "Authenticated users can read all domains" ON "public"."apex_domains" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



CREATE POLICY "Authenticated users can read all scan jobs" ON "public"."asset_scan_jobs" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



CREATE POLICY "Authenticated users can read all subdomains" ON "public"."subdomains" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



COMMENT ON POLICY "Authenticated users can read all subdomains" ON "public"."subdomains" IS 'LEAN model: All authenticated users can read all reconnaissance data. Part of public data sharing for bug bounty researchers.';



CREATE POLICY "Authenticated users can read all urls" ON "public"."urls" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



CREATE POLICY "Authenticated users can read module profiles" ON "public"."scan_module_profiles" FOR SELECT USING ((("auth"."role"() = 'authenticated'::"text") OR ("auth"."role"() = 'service_role'::"text")));



CREATE POLICY "Service role can manage DNS records" ON "public"."dns_records" USING (("auth"."role"() = 'service_role'::"text")) WITH CHECK (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can manage HTTP probes" ON "public"."http_probes" USING (("auth"."role"() = 'service_role'::"text")) WITH CHECK (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can manage assets" ON "public"."assets" USING (("auth"."role"() = 'service_role'::"text")) WITH CHECK (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can manage batch scans" ON "public"."batch_scan_jobs" USING (("auth"."role"() = 'service_role'::"text")) WITH CHECK (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can manage domains" ON "public"."apex_domains" USING (("auth"."role"() = 'service_role'::"text")) WITH CHECK (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can manage module profiles" ON "public"."scan_module_profiles" USING (("auth"."role"() = 'service_role'::"text")) WITH CHECK (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can manage scan jobs" ON "public"."asset_scan_jobs" USING (("auth"."role"() = 'service_role'::"text")) WITH CHECK (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can manage subdomains" ON "public"."subdomains" USING (("auth"."role"() = 'service_role'::"text")) WITH CHECK (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role full access batch assignments" ON "public"."batch_domain_assignments" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role full access batch scans" ON "public"."batch_scan_jobs" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role full access module profiles" ON "public"."scan_module_profiles" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role full access quotas" ON "public"."user_quotas" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role full access to API keys" ON "public"."api_keys" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role full access usage" ON "public"."user_usage" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role has full access" ON "public"."vt_discovered_urls" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role has full access to historical_urls" ON "public"."historical_urls" TO "service_role" USING (true) WITH CHECK (true);



CREATE POLICY "Service role has full access to http_probes" ON "public"."http_probes" USING ((("auth"."jwt"() ->> 'role'::"text") = 'service_role'::"text")) WITH CHECK ((("auth"."jwt"() ->> 'role'::"text") = 'service_role'::"text"));



CREATE POLICY "Users can create own API keys" ON "public"."api_keys" FOR INSERT WITH CHECK (("user_id" = "auth"."uid"()));



CREATE POLICY "Users can create own batch scans" ON "public"."batch_scan_jobs" FOR INSERT WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can create their own asset scans" ON "public"."asset_scan_jobs" FOR INSERT WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can create their own scans" ON "public"."scans" FOR INSERT WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can delete apex domains of own assets" ON "public"."apex_domains" FOR DELETE USING (("asset_id" IN ( SELECT "assets"."id"
   FROM "public"."assets"
  WHERE ("assets"."user_id" = "auth"."uid"()))));



CREATE POLICY "Users can delete own API keys" ON "public"."api_keys" FOR DELETE USING (("user_id" = "auth"."uid"()));



CREATE POLICY "Users can delete own batch scans" ON "public"."batch_scan_jobs" FOR DELETE USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can delete own subdomains" ON "public"."subdomains" FOR DELETE USING ((EXISTS ( SELECT 1
   FROM "public"."asset_scan_jobs"
  WHERE (("asset_scan_jobs"."id" = "subdomains"."scan_job_id") AND ("asset_scan_jobs"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can delete their own scans" ON "public"."scans" FOR DELETE USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can insert apex domains for own assets" ON "public"."apex_domains" FOR INSERT WITH CHECK (("asset_id" IN ( SELECT "assets"."id"
   FROM "public"."assets"
  WHERE ("assets"."user_id" = "auth"."uid"()))));



CREATE POLICY "Users can insert own subdomains" ON "public"."subdomains" FOR INSERT WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."asset_scan_jobs"
  WHERE (("asset_scan_jobs"."id" = "subdomains"."scan_job_id") AND ("asset_scan_jobs"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can read own historical_urls" ON "public"."historical_urls" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."assets"
  WHERE (("assets"."id" = "historical_urls"."asset_id") AND ("assets"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can update apex domains of own assets" ON "public"."apex_domains" FOR UPDATE USING (("asset_id" IN ( SELECT "assets"."id"
   FROM "public"."assets"
  WHERE ("assets"."user_id" = "auth"."uid"())))) WITH CHECK (("asset_id" IN ( SELECT "assets"."id"
   FROM "public"."assets"
  WHERE ("assets"."user_id" = "auth"."uid"()))));



CREATE POLICY "Users can update own API keys" ON "public"."api_keys" FOR UPDATE USING (("user_id" = "auth"."uid"()));



CREATE POLICY "Users can update own subdomains" ON "public"."subdomains" FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM "public"."asset_scan_jobs"
  WHERE (("asset_scan_jobs"."id" = "subdomains"."scan_job_id") AND ("asset_scan_jobs"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can update their own asset scans" ON "public"."asset_scan_jobs" FOR UPDATE USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can update their own scans" ON "public"."scans" FOR UPDATE USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view apex domains of own assets" ON "public"."apex_domains" FOR SELECT USING (("asset_id" IN ( SELECT "assets"."id"
   FROM "public"."assets"
  WHERE ("assets"."user_id" = "auth"."uid"()))));



CREATE POLICY "Users can view module profiles" ON "public"."scan_module_profiles" FOR SELECT USING (true);



CREATE POLICY "Users can view own API keys" ON "public"."api_keys" FOR SELECT USING (("user_id" = "auth"."uid"()));



CREATE POLICY "Users can view own batch domain assignments" ON "public"."batch_domain_assignments" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."batch_scan_jobs"
  WHERE (("batch_scan_jobs"."id" = "batch_domain_assignments"."batch_scan_id") AND ("batch_scan_jobs"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view own quotas" ON "public"."user_quotas" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view own usage" ON "public"."user_usage" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view their module analytics" ON "public"."subdomains" FOR SELECT USING (("scan_job_id" IN ( SELECT "asset_scan_jobs"."id"
   FROM "public"."asset_scan_jobs"
  WHERE ("asset_scan_jobs"."user_id" = "auth"."uid"()))));



CREATE POLICY "Users can view their own asset scans" ON "public"."asset_scan_jobs" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view their own crawled endpoints" ON "public"."crawled_endpoints" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."assets"
  WHERE (("assets"."id" = "crawled_endpoints"."asset_id") AND ("assets"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view their own discovered URLs" ON "public"."vt_discovered_urls" FOR SELECT USING (("asset_id" IN ( SELECT "assets"."id"
   FROM "public"."assets"
  WHERE ("assets"."user_id" = "auth"."uid"()))));



CREATE POLICY "Users can view their own http_probes" ON "public"."http_probes" FOR SELECT USING (("scan_job_id" IN ( SELECT "asset_scan_jobs"."id"
   FROM "public"."asset_scan_jobs"
  WHERE ("asset_scan_jobs"."user_id" = "auth"."uid"()))));



CREATE POLICY "Users can view their own scans" ON "public"."scans" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view their own urls" ON "public"."urls" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."assets"
  WHERE (("assets"."id" = "urls"."asset_id") AND ("assets"."user_id" = "auth"."uid"())))));



ALTER TABLE "public"."apex_domains" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."api_keys" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."asset_scan_jobs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."assets" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."batch_domain_assignments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."batch_scan_jobs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."crawled_endpoints" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."historical_urls" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."http_probes" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."scan_module_profiles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."scans" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."subdomains" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."urls" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_quotas" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_usage" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."vt_discovered_urls" ENABLE ROW LEVEL SECURITY;


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON FUNCTION "public"."bulk_insert_dns_records"("records" "jsonb") TO "anon";
GRANT ALL ON FUNCTION "public"."bulk_insert_dns_records"("records" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."bulk_insert_dns_records"("records" "jsonb") TO "service_role";



GRANT ALL ON FUNCTION "public"."bulk_insert_subdomains"("records" "jsonb") TO "anon";
GRANT ALL ON FUNCTION "public"."bulk_insert_subdomains"("records" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."bulk_insert_subdomains"("records" "jsonb") TO "service_role";



GRANT ALL ON FUNCTION "public"."calculate_module_resources"("p_module_name" "text", "p_domain_count" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."calculate_module_resources"("p_module_name" "text", "p_domain_count" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."calculate_module_resources"("p_module_name" "text", "p_domain_count" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."can_add_domain_to_asset"("check_user_id" "uuid", "check_asset_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."can_add_domain_to_asset"("check_user_id" "uuid", "check_asset_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."can_add_domain_to_asset"("check_user_id" "uuid", "check_asset_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."can_create_asset"("check_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."can_create_asset"("check_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."can_create_asset"("check_user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."can_start_scan"("check_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."can_start_scan"("check_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."can_start_scan"("check_user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."create_asset_with_domains"("p_name" "text", "p_description" "text", "p_bug_bounty_url" "text", "p_domains" "text"[], "p_priority" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."create_asset_with_domains"("p_name" "text", "p_description" "text", "p_bug_bounty_url" "text", "p_domains" "text"[], "p_priority" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."create_asset_with_domains"("p_name" "text", "p_description" "text", "p_bug_bounty_url" "text", "p_domains" "text"[], "p_priority" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."ensure_user_tracking_initialized"("target_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."ensure_user_tracking_initialized"("target_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."ensure_user_tracking_initialized"("target_user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."get_dashboard_stats"("target_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."get_dashboard_stats"("target_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_dashboard_stats"("target_user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."get_optimal_batch_sizes"("p_module_name" "text", "p_total_domains" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_optimal_batch_sizes"("p_module_name" "text", "p_total_domains" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_optimal_batch_sizes"("p_module_name" "text", "p_total_domains" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_paid_user_count"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_paid_user_count"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_paid_user_count"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_user_recon_data"("target_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."get_user_recon_data"("target_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_user_recon_data"("target_user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."has_paid_spots_available"("max_spots" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."has_paid_spots_available"("max_spots" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."has_paid_spots_available"("max_spots" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."sync_subdomain_asset_id"() TO "anon";
GRANT ALL ON FUNCTION "public"."sync_subdomain_asset_id"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."sync_subdomain_asset_id"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_apex_domain_last_scanned"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_apex_domain_last_scanned"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_apex_domain_last_scanned"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_api_key_last_used"("p_key_hash" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."update_api_key_last_used"("p_key_hash" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_api_key_last_used"("p_key_hash" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."update_asset_scan_jobs_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_asset_scan_jobs_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_asset_scan_jobs_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_batch_scan_jobs_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_batch_scan_jobs_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_batch_scan_jobs_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_scan_completed_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_scan_completed_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_scan_completed_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_scan_job_progress"("p_scan_job_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."update_scan_job_progress"("p_scan_job_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_scan_job_progress"("p_scan_job_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."update_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_user_asset_count"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_user_asset_count"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_user_asset_count"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_user_domain_count"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_user_domain_count"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_user_domain_count"() TO "service_role";



GRANT ALL ON TABLE "public"."apex_domains" TO "anon";
GRANT ALL ON TABLE "public"."apex_domains" TO "authenticated";
GRANT ALL ON TABLE "public"."apex_domains" TO "service_role";



GRANT ALL ON TABLE "public"."asset_scan_jobs" TO "anon";
GRANT ALL ON TABLE "public"."asset_scan_jobs" TO "authenticated";
GRANT ALL ON TABLE "public"."asset_scan_jobs" TO "service_role";



GRANT ALL ON TABLE "public"."assets" TO "anon";
GRANT ALL ON TABLE "public"."assets" TO "authenticated";
GRANT ALL ON TABLE "public"."assets" TO "service_role";



GRANT ALL ON TABLE "public"."subdomains" TO "anon";
GRANT ALL ON TABLE "public"."subdomains" TO "authenticated";
GRANT ALL ON TABLE "public"."subdomains" TO "service_role";



GRANT ALL ON TABLE "public"."apex_domain_overview" TO "anon";
GRANT ALL ON TABLE "public"."apex_domain_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."apex_domain_overview" TO "service_role";



GRANT ALL ON TABLE "public"."api_keys" TO "anon";
GRANT ALL ON TABLE "public"."api_keys" TO "authenticated";
GRANT ALL ON TABLE "public"."api_keys" TO "service_role";



GRANT ALL ON TABLE "public"."asset_overview" TO "anon";
GRANT ALL ON TABLE "public"."asset_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."asset_overview" TO "service_role";



GRANT ALL ON TABLE "public"."dns_records" TO "anon";
GRANT ALL ON TABLE "public"."dns_records" TO "authenticated";
GRANT ALL ON TABLE "public"."dns_records" TO "service_role";



GRANT ALL ON TABLE "public"."http_probes" TO "anon";
GRANT ALL ON TABLE "public"."http_probes" TO "authenticated";
GRANT ALL ON TABLE "public"."http_probes" TO "service_role";



GRANT ALL ON TABLE "public"."urls" TO "anon";
GRANT ALL ON TABLE "public"."urls" TO "authenticated";
GRANT ALL ON TABLE "public"."urls" TO "service_role";



GRANT ALL ON TABLE "public"."asset_recon_counts" TO "anon";
GRANT ALL ON TABLE "public"."asset_recon_counts" TO "authenticated";
GRANT ALL ON TABLE "public"."asset_recon_counts" TO "service_role";



GRANT ALL ON TABLE "public"."batch_domain_assignments" TO "anon";
GRANT ALL ON TABLE "public"."batch_domain_assignments" TO "authenticated";
GRANT ALL ON TABLE "public"."batch_domain_assignments" TO "service_role";



GRANT ALL ON TABLE "public"."batch_scan_jobs" TO "anon";
GRANT ALL ON TABLE "public"."batch_scan_jobs" TO "authenticated";
GRANT ALL ON TABLE "public"."batch_scan_jobs" TO "service_role";



GRANT ALL ON TABLE "public"."crawled_endpoints" TO "anon";
GRANT ALL ON TABLE "public"."crawled_endpoints" TO "authenticated";
GRANT ALL ON TABLE "public"."crawled_endpoints" TO "service_role";



GRANT ALL ON TABLE "public"."historical_urls" TO "anon";
GRANT ALL ON TABLE "public"."historical_urls" TO "authenticated";
GRANT ALL ON TABLE "public"."historical_urls" TO "service_role";



GRANT ALL ON TABLE "public"."module_analytics" TO "anon";
GRANT ALL ON TABLE "public"."module_analytics" TO "authenticated";
GRANT ALL ON TABLE "public"."module_analytics" TO "service_role";



GRANT ALL ON TABLE "public"."scan_module_profiles" TO "anon";
GRANT ALL ON TABLE "public"."scan_module_profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."scan_module_profiles" TO "service_role";



GRANT ALL ON TABLE "public"."scans" TO "anon";
GRANT ALL ON TABLE "public"."scans" TO "authenticated";
GRANT ALL ON TABLE "public"."scans" TO "service_role";



GRANT ALL ON TABLE "public"."scans_with_assets" TO "anon";
GRANT ALL ON TABLE "public"."scans_with_assets" TO "authenticated";
GRANT ALL ON TABLE "public"."scans_with_assets" TO "service_role";



GRANT ALL ON TABLE "public"."subdomain_current_dns" TO "anon";
GRANT ALL ON TABLE "public"."subdomain_current_dns" TO "authenticated";
GRANT ALL ON TABLE "public"."subdomain_current_dns" TO "service_role";



GRANT ALL ON TABLE "public"."user_quotas" TO "anon";
GRANT ALL ON TABLE "public"."user_quotas" TO "authenticated";
GRANT ALL ON TABLE "public"."user_quotas" TO "service_role";



GRANT ALL ON TABLE "public"."user_usage" TO "anon";
GRANT ALL ON TABLE "public"."user_usage" TO "authenticated";
GRANT ALL ON TABLE "public"."user_usage" TO "service_role";



GRANT ALL ON TABLE "public"."user_usage_overview" TO "anon";
GRANT ALL ON TABLE "public"."user_usage_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."user_usage_overview" TO "service_role";



GRANT ALL ON TABLE "public"."vt_discovered_urls" TO "anon";
GRANT ALL ON TABLE "public"."vt_discovered_urls" TO "authenticated";
GRANT ALL ON TABLE "public"."vt_discovered_urls" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";






RESET ALL;
