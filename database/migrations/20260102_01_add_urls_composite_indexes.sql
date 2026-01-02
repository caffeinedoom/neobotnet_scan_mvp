-- Migration: Add composite indexes to all major tables for better query performance
-- Date: 2026-01-02
-- Purpose: Fix statement timeout when filtering by asset_id with ordering
-- Note: Run in Supabase SQL Editor (remove CONCURRENTLY for Supabase compatibility)

-- ================================================================
-- URLS TABLE INDEXES
-- ================================================================

-- Composite index for asset_id + first_discovered_at (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_urls_asset_discovered 
ON public.urls (asset_id, first_discovered_at DESC);

-- Composite index for asset_id + is_alive
CREATE INDEX IF NOT EXISTS idx_urls_asset_alive 
ON public.urls (asset_id, is_alive);

-- Composite index for asset_id + status_code
CREATE INDEX IF NOT EXISTS idx_urls_asset_status 
ON public.urls (asset_id, status_code);

-- Composite index for asset_id + has_params
CREATE INDEX IF NOT EXISTS idx_urls_asset_params 
ON public.urls (asset_id, has_params);

-- ================================================================
-- HTTP_PROBES TABLE INDEXES
-- ================================================================

-- Composite index for asset_id + created_at (pagination ordering)
CREATE INDEX IF NOT EXISTS idx_http_probes_asset_created 
ON public.http_probes (asset_id, created_at DESC);

-- Composite index for asset_id + status_code (common filter)
CREATE INDEX IF NOT EXISTS idx_http_probes_asset_status 
ON public.http_probes (asset_id, status_code);

-- ================================================================
-- SUBDOMAINS TABLE INDEXES
-- ================================================================

-- Composite index for scan_job_id + discovered_at (pagination ordering)
CREATE INDEX IF NOT EXISTS idx_subdomains_scanjob_discovered 
ON public.subdomains (scan_job_id, discovered_at DESC);

-- Index for parent_domain filter + ordering
CREATE INDEX IF NOT EXISTS idx_subdomains_parent_discovered 
ON public.subdomains (parent_domain, discovered_at DESC);

-- ================================================================
-- DNS_RECORDS TABLE INDEXES
-- ================================================================

-- Composite index for asset_id + resolved_at (pagination ordering)
CREATE INDEX IF NOT EXISTS idx_dns_records_asset_resolved 
ON public.dns_records (asset_id, resolved_at DESC);

-- Composite index for asset_id + record_type (common filter)
CREATE INDEX IF NOT EXISTS idx_dns_records_asset_type 
ON public.dns_records (asset_id, record_type);

-- Index for subdomain searches + ordering
CREATE INDEX IF NOT EXISTS idx_dns_records_subdomain_resolved 
ON public.dns_records (subdomain, resolved_at DESC);

-- ================================================================
-- ASSET_SCAN_JOBS TABLE INDEXES (used in subdomains join)
-- ================================================================

-- Composite index for asset_id + created_at
CREATE INDEX IF NOT EXISTS idx_asset_scan_jobs_asset_created 
ON public.asset_scan_jobs (asset_id, created_at DESC);
