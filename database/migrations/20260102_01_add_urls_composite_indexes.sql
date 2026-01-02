-- Migration: Add composite indexes to urls table for better query performance
-- Date: 2026-01-02
-- Purpose: Fix statement timeout when filtering URLs by asset_id with ordering

-- Composite index for asset_id + first_discovered_at (most common query pattern)
-- This speeds up: WHERE asset_id = ? ORDER BY first_discovered_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_urls_asset_discovered 
ON public.urls (asset_id, first_discovered_at DESC);

-- Composite index for asset_id + is_alive (common filter combination)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_urls_asset_alive 
ON public.urls (asset_id, is_alive);

-- Composite index for asset_id + status_code (common filter combination)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_urls_asset_status 
ON public.urls (asset_id, status_code);

-- Composite index for asset_id + has_params (common filter combination)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_urls_asset_params 
ON public.urls (asset_id, has_params);
