import { apiClient } from './client';
import { API_ENDPOINTS } from './config';

// ================================================================
// Unified Reconnaissance Data Types
// ================================================================

export interface ReconSummary {
  total_assets: number;
  active_assets: number;
  total_domains: number;
  active_domains: number;
  total_scans: number;
  completed_scans: number;
  failed_scans: number;
  pending_scans: number;
  total_subdomains: number;
  total_probes: number;  // HTTP probes = live servers
  total_dns_records: number;
  total_urls: number;    // Discovered URLs from crawlers
  last_scan_date?: string;
}

export interface ReconAsset {
  id: string;
  name: string;
  description?: string;
  bug_bounty_url?: string;
  is_active: boolean;
  priority: number;
  tags: string[];
  created_at: string;
  updated_at: string;
  apex_domain_count: number;
  active_domain_count: number;
  total_scans: number;
  completed_scans: number;
  failed_scans: number;
  pending_scans: number;
  total_subdomains: number;
  total_probes: number;  // HTTP probes = live servers
  total_dns_records: number;
  total_urls: number;    // Discovered URLs from crawlers
  last_scan_date?: string;
}

export interface ReconScan {
  id: string;
  asset_id: string;
  asset_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  modules: string[];
  total_domains: number;
  completed_domains: number;
  active_domains_only: boolean;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  estimated_completion?: string;
  error_message?: string;
  progress_percentage: number;
  subdomains_found: number;
  scan_type: string;
}

export interface ReconData {
  summary: ReconSummary;
  assets: ReconAsset[];
  recent_scans: ReconScan[];
}

// ================================================================
// Unified Reconnaissance Data Service
// ================================================================

class ReconDataService {
  private cache: ReconData | null = null;
  private lastFetch: number = 0;
  private CACHE_DURATION = 30000; // 30 seconds cache
  private isLoading: boolean = false;
  private pendingPromise: Promise<ReconData> | null = null;

  /**
   * Get comprehensive reconnaissance data with smart caching.
   * 
   * This single method serves all reconnaissance pages:
   * - Dashboard: Uses summary statistics
   * - Assets: Uses assets array + summary statistics
   * - Scans: Uses recent_scans + assets + summary statistics
   * 
   * Features:
   * - Smart caching prevents redundant API calls
   * - Deduplication prevents multiple concurrent requests
   * - Force refresh for real-time updates after user actions
   */
  async getReconData(forceRefresh = false): Promise<ReconData> {
    const now = Date.now();
    
    // Return cached data if recent and not forcing refresh
    if (!forceRefresh && this.cache && (now - this.lastFetch) < this.CACHE_DURATION) {
      console.log('🎯 ReconDataService: Using cached data');
      return this.cache;
    }

    // If already loading, return the pending promise to prevent duplicate requests
    if (this.isLoading && this.pendingPromise) {
      console.log('🔄 ReconDataService: Request already in progress, returning pending promise');
      return this.pendingPromise;
    }

    // Mark as loading and create new promise
    this.isLoading = true;
    this.pendingPromise = this.fetchFreshData();

    try {
      const data = await this.pendingPromise;
      return data;
    } finally {
      this.isLoading = false;
      this.pendingPromise = null;
    }
  }

  private async fetchFreshData(): Promise<ReconData> {
    console.log('🚀 ReconDataService: Fetching fresh data from unified endpoint');
    
    try {
      const response = await apiClient.get(API_ENDPOINTS.USAGE.RECON_DATA);
      const data: ReconData = response.data;
      
      // Update cache
      this.cache = data;
      this.lastFetch = Date.now();
      
      console.log('✅ ReconDataService: Fresh data cached successfully', {
        assets: data.assets.length,
        scans: data.recent_scans.length,
        total_subdomains: data.summary.total_subdomains
      });
      
      return data;
    } catch (error) {
      console.error('❌ ReconDataService: Failed to fetch data', error);
      
      // Return cached data if available, otherwise throw
      if (this.cache) {
        console.log('⚠️ ReconDataService: Returning stale cached data due to error');
        return this.cache;
      }
      
      throw error;
    }
  }

  // ================================================================
  // Page-Specific Data Getters
  // ================================================================

  /**
   * Get data for Dashboard page.
   * Returns summary statistics optimized for dashboard counters.
   */
  async getDashboardData(forceRefresh = false): Promise<ReconSummary> {
    const data = await this.getReconData(forceRefresh);
    return data.summary;
  }

  /**
   * Get data for Assets page.
   * Returns individual assets with statistics + summary for top counters.
   */
  async getAssetsData(forceRefresh = false): Promise<{
    assets: ReconAsset[];
    summary: ReconSummary;
  }> {
    const data = await this.getReconData(forceRefresh);
    return {
      assets: data.assets,
      summary: data.summary
    };
  }

  /**
   * Get data for Scans page.
   * Returns recent scans + assets for scanning + summary for top counters.
   */
  async getScansData(forceRefresh = false): Promise<{
    summary: ReconSummary;
    assets: ReconAsset[];
    recent_scans: ReconScan[];
  }> {
    const data = await this.getReconData(forceRefresh);
    return {
      summary: data.summary,
      assets: data.assets,
      recent_scans: data.recent_scans
    };
  }

  /**
   * Get data for Asset Detail page.
   * Returns individual asset with CONSISTENT statistics using unified counting logic.
   * 
   * This ensures asset detail page shows IDENTICAL counts as dashboard/assets:
   * - Scans = unique sessions (not per domain) 
   * - Subdomains = full count (no 1000 limit)
   * - Same database stored procedure as other pages
   */
  async getAssetDetailData(assetId: string, forceRefresh = false): Promise<ReconAsset | null> {
    const data = await this.getReconData(forceRefresh);
    return data.assets.find(asset => asset.id === assetId) || null;
  }

  // ================================================================
  // Cache Management
  // ================================================================

  /**
   * Force refresh for all pages.
   * Call this after user actions that modify data (create asset, start scan, etc.)
   */
  invalidateCache(): void {
    console.log('🔄 ReconDataService: Cache invalidated - next request will fetch fresh data');
    this.cache = null;
    this.lastFetch = 0;
  }

  /**
   * Get cache status for debugging.
   */
  getCacheStatus(): {
    hasCachedData: boolean;
    cacheAge: number;
    isStale: boolean;
  } {
    const now = Date.now();
    const cacheAge = this.cache ? now - this.lastFetch : 0;
    const isStale = cacheAge > this.CACHE_DURATION;

    return {
      hasCachedData: !!this.cache,
      cacheAge,
      isStale
    };
  }

  /**
   * Preload data for better UX.
   * Call this on app initialization or user login.
   */
  async preloadData(): Promise<void> {
    try {
      await this.getReconData();
      console.log('🚀 ReconDataService: Data preloaded successfully');
    } catch (error) {
      console.error('❌ ReconDataService: Failed to preload data', error);
      // Don't throw - this is just a performance optimization
    }
  }
}

// ================================================================
// Service Instance & Exports
// ================================================================

// Export singleton instance directly
export const reconDataService = new ReconDataService();

// Default export for convenience
export default reconDataService;

// ================================================================
// Legacy Compatibility Types
// ================================================================

// For backward compatibility with existing code
export type DashboardStatistics = ReconSummary;
export type AssetWithStats = ReconAsset;
export type AssetScanJob = ReconScan;

// ================================================================
// All types are already exported above as interfaces
// ================================================================
