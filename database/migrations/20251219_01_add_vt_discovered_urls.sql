-- ============================================================
-- Migration: Add vt_discovered_urls table
-- Module: TYVT (VirusTotal Domain Scanner)
-- Date: 2025-12-19
-- ============================================================
-- Description:
--   This table stores URLs discovered from VirusTotal's domain report API.
--   These are historical URLs that VT has seen associated with each subdomain,
--   making them valuable for reconnaissance and vulnerability discovery.
-- ============================================================

-- Create the vt_discovered_urls table
CREATE TABLE IF NOT EXISTS vt_discovered_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign keys
    scan_job_id UUID NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    
    -- The subdomain that was queried
    subdomain TEXT NOT NULL,
    
    -- The discovered URL
    url TEXT NOT NULL,
    
    -- VirusTotal scan information
    positives INTEGER DEFAULT 0,  -- Number of AV engines that flagged this URL
    total INTEGER DEFAULT 0,      -- Total number of AV engines
    vt_scan_date TEXT,            -- When VT scanned this URL (VT's date format)
    
    -- Metadata
    source TEXT DEFAULT 'virustotal',
    discovered_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Unique constraint: one URL per asset (prevents duplicates across scans)
    CONSTRAINT vt_discovered_urls_unique UNIQUE (url, asset_id)
);

-- ============================================================
-- Indexes
-- ============================================================

-- Fast lookup by asset
CREATE INDEX IF NOT EXISTS idx_vt_discovered_urls_asset_id 
    ON vt_discovered_urls(asset_id);

-- Fast lookup by scan job
CREATE INDEX IF NOT EXISTS idx_vt_discovered_urls_scan_job_id 
    ON vt_discovered_urls(scan_job_id);

-- Fast lookup by subdomain within an asset
CREATE INDEX IF NOT EXISTS idx_vt_discovered_urls_subdomain 
    ON vt_discovered_urls(asset_id, subdomain);

-- Lookup by discovery date (for time-based queries)
CREATE INDEX IF NOT EXISTS idx_vt_discovered_urls_discovered_at 
    ON vt_discovered_urls(discovered_at DESC);

-- ============================================================
-- Row Level Security
-- ============================================================

ALTER TABLE vt_discovered_urls ENABLE ROW LEVEL SECURITY;

-- Users can only see their own discovered URLs (via asset ownership)
CREATE POLICY "Users can view their own discovered URLs"
    ON vt_discovered_urls
    FOR SELECT
    USING (
        asset_id IN (
            SELECT id FROM assets WHERE user_id = auth.uid()
        )
    );

-- Service role can do everything (for scanner writes)
CREATE POLICY "Service role has full access"
    ON vt_discovered_urls
    FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON TABLE vt_discovered_urls IS 'URLs discovered from VirusTotal domain reports - historical paths for recon';
COMMENT ON COLUMN vt_discovered_urls.subdomain IS 'The subdomain that was queried (e.g., api.example.com)';
COMMENT ON COLUMN vt_discovered_urls.url IS 'The discovered URL from VT undetected_urls';
COMMENT ON COLUMN vt_discovered_urls.positives IS 'Number of AV engines that detected this URL as malicious';
COMMENT ON COLUMN vt_discovered_urls.total IS 'Total number of AV engines that scanned this URL';
COMMENT ON COLUMN vt_discovered_urls.vt_scan_date IS 'When VirusTotal originally scanned this URL';

