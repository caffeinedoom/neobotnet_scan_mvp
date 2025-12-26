-- Migration: Create historical_urls table
-- Date: 2025-12-22
-- Description: Stores raw URL discoveries from Waymore (Wayback Machine, Common Crawl, etc.)
--              before probing by URL Resolver. Tracks source provenance and enables deduplication.

-- ============================================================================
-- TABLE: historical_urls
-- ============================================================================
-- Purpose: Store historical URL discoveries from archive sources
-- Data Flow: Waymore → historical_urls → Redis Stream → URL Resolver → urls table

CREATE TABLE IF NOT EXISTS historical_urls (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core URL data
    url TEXT NOT NULL,
    parent_domain TEXT NOT NULL,
    
    -- Source tracking
    -- Values: 'wayback', 'commoncrawl', 'alienvault', 'urlscan', 'virustotal', 'intelligencex'
    source TEXT NOT NULL DEFAULT 'waymore',
    
    -- Archive metadata (when available from source)
    archive_timestamp TIMESTAMPTZ,  -- Original archive date from Wayback/CC
    
    -- Relationships
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    scan_job_id UUID,  -- Links to batch_scan_jobs or asset_scan_jobs
    
    -- Timestamps
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Flexible metadata storage
    metadata JSONB DEFAULT '{}',
    
    -- Deduplication: same URL per asset only stored once
    -- Re-discoveries update the discovered_at timestamp
    UNIQUE(url, asset_id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Asset-level queries (most common)
CREATE INDEX IF NOT EXISTS idx_historical_urls_asset_id 
    ON historical_urls(asset_id);

-- Parent domain filtering
CREATE INDEX IF NOT EXISTS idx_historical_urls_parent_domain 
    ON historical_urls(parent_domain);

-- Scan job linkage
CREATE INDEX IF NOT EXISTS idx_historical_urls_scan_job_id 
    ON historical_urls(scan_job_id);

-- Source filtering (e.g., "show all Wayback discoveries")
CREATE INDEX IF NOT EXISTS idx_historical_urls_source 
    ON historical_urls(source);

-- Recent discoveries (dashboard, reporting)
CREATE INDEX IF NOT EXISTS idx_historical_urls_discovered_at 
    ON historical_urls(discovered_at DESC);

-- Composite index for common query pattern
CREATE INDEX IF NOT EXISTS idx_historical_urls_asset_source 
    ON historical_urls(asset_id, source);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE historical_urls ENABLE ROW LEVEL SECURITY;

-- Service role has full access (for backend operations)
CREATE POLICY "Service role has full access to historical_urls"
    ON historical_urls
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Users can read their own historical URLs (via asset ownership)
CREATE POLICY "Users can read own historical_urls"
    ON historical_urls
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM assets 
            WHERE assets.id = historical_urls.asset_id 
            AND assets.user_id = auth.uid()
        )
    );

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE historical_urls IS 
    'Stores historical URL discoveries from Waymore (Wayback Machine, Common Crawl, etc.)';

COMMENT ON COLUMN historical_urls.url IS 
    'The discovered URL (full URL including path and query params)';

COMMENT ON COLUMN historical_urls.parent_domain IS 
    'The apex domain this URL belongs to (e.g., example.com)';

COMMENT ON COLUMN historical_urls.source IS 
    'Archive source: wayback, commoncrawl, alienvault, urlscan, virustotal, intelligencex';

COMMENT ON COLUMN historical_urls.archive_timestamp IS 
    'Original archive timestamp from the source (when available)';

COMMENT ON COLUMN historical_urls.metadata IS 
    'Flexible JSON storage for source-specific metadata';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'historical_urls') THEN
        RAISE NOTICE 'SUCCESS: historical_urls table created';
    ELSE
        RAISE EXCEPTION 'FAILED: historical_urls table was not created';
    END IF;
END $$;


