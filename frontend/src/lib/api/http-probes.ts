import { apiClient } from './client';
import type {
  HTTPProbe,
  HTTPProbeStats,
  HTTPProbeQueryParams,
  HTTPProbeListResponse,
  HTTPProbeCacheEntry,
  HTTPProbeFetchOptions,
} from '@/types/http-probes';

// ================================================================
// HTTP Probes Service with Smart Caching
// ================================================================

/**
 * HTTP Probes Service Class
 * 
 * Provides HTTP probe fetching with intelligent caching to minimize
 * API calls and improve performance.
 * 
 * Cache Strategy:
 * - Per-query caching with 5-minute TTL
 * - Parallel fetching for multiple queries
 * - Automatic cache invalidation on expiry
 */
class HTTPProbesService {
  private cache: Map<string, HTTPProbeCacheEntry> = new Map();
  private CACHE_TTL = 5 * 60 * 1000; // 5 minutes in milliseconds
  private pendingRequests: Map<string, Promise<HTTPProbeListResponse>> = new Map();

  /**
   * Generate cache key from query parameters
   */
  private getCacheKey(params?: HTTPProbeQueryParams): string {
    if (!params) return 'default';
    
    const sortedParams = Object.keys(params)
      .sort()
      .map(key => `${key}=${params[key as keyof HTTPProbeQueryParams]}`)
      .join('&');
    
    return sortedParams || 'default';
  }

  /**
   * Check if cache entry is valid
   */
  private isCacheValid(entry: HTTPProbeCacheEntry): boolean {
    return Date.now() - entry.timestamp < this.CACHE_TTL;
  }

  /**
   * Fetch HTTP probes with filters and pagination
   * 
   * @param params - Query parameters (pagination, filters)
   * @param options - Fetch options (cache control)
   * @returns List of HTTP probes
   */
  async fetchHTTPProbes(
    params?: HTTPProbeQueryParams,
    options?: HTTPProbeFetchOptions
  ): Promise<HTTPProbeListResponse> {
    const cacheKey = this.getCacheKey(params);

    // Check cache first (unless force refresh)
    if (!options?.forceRefresh) {
      const cached = this.cache.get(cacheKey);
      if (cached && this.isCacheValid(cached)) {
        return cached.data;
      }
    }

    // Check if there's already a pending request for this query
    if (this.pendingRequests.has(cacheKey)) {
      return this.pendingRequests.get(cacheKey)!;
    }

    try {
      // Build query string
      const queryParams = new URLSearchParams();
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset) queryParams.append('offset', params.offset.toString());
      if (params?.asset_id) queryParams.append('asset_id', params.asset_id);
      if (params?.parent_domain) queryParams.append('parent_domain', params.parent_domain);
      if (params?.scan_job_id) queryParams.append('scan_job_id', params.scan_job_id);
      if (params?.status_code) queryParams.append('status_code', params.status_code.toString());
      if (params?.scheme) queryParams.append('scheme', params.scheme);
      if (params?.technology) queryParams.append('technology', params.technology);
      if (params?.has_redirect !== undefined) queryParams.append('has_redirect', params.has_redirect.toString());
      if (params?.cdn_name) queryParams.append('cdn_name', params.cdn_name);

      const endpoint = '/api/v1/http-probes';
      const url = queryParams.toString() ? `${endpoint}?${queryParams}` : endpoint;

      // Create the request promise
      const requestPromise = apiClient.get<HTTPProbeListResponse>(url, {
        signal: options?.signal,
      }).then((response) => response.data);

      // Store it to prevent duplicate requests
      this.pendingRequests.set(cacheKey, requestPromise);

      try {
        const data = await requestPromise;
        
        // Cache the result
        this.cache.set(cacheKey, {
          data,
          timestamp: Date.now(),
          params: params || {},
        });

        return data;
      } finally {
        // Clean up pending request
        this.pendingRequests.delete(cacheKey);
      }
    } catch (error) {
      console.error('Error fetching HTTP probes:', error);
      throw error;
    }
  }

  /**
   * Fetch a single HTTP probe by ID
   * 
   * @param probeId - HTTP probe UUID
   * @returns Single HTTP probe
   */
  async fetchHTTPProbeById(probeId: string): Promise<HTTPProbe> {
    try {
      const response = await apiClient.get<HTTPProbe>(`/api/v1/http-probes/${probeId}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching HTTP probe ${probeId}:`, error);
      throw error;
    }
  }

  /**
   * Fetch HTTP probe statistics
   * 
   * @param params - Filter parameters (asset_id, scan_job_id)
   * @returns Aggregate statistics
   */
  async fetchHTTPProbeStats(params?: {
    asset_id?: string;
    scan_job_id?: string;
  }): Promise<HTTPProbeStats> {
    try {
      const queryParams = new URLSearchParams();
      if (params?.asset_id) queryParams.append('asset_id', params.asset_id);
      if (params?.scan_job_id) queryParams.append('scan_job_id', params.scan_job_id);

      const url = queryParams.toString()
        ? `/api/v1/http-probes/stats/summary?${queryParams}`
        : '/api/v1/http-probes/stats/summary';

      const response = await apiClient.get<HTTPProbeStats>(url);
      return response.data;
    } catch (error) {
      console.error('Error fetching HTTP probe stats:', error);
      throw error;
    }
  }

  /**
   * Fetch HTTP probes for a specific asset
   * 
   * Convenience method for asset-specific queries.
   * 
   * @param assetId - Asset UUID
   * @param params - Additional query parameters
   * @returns List of HTTP probes for the asset
   */
  async fetchHTTPProbesByAsset(
    assetId: string,
    params?: Omit<HTTPProbeQueryParams, 'asset_id'>,
    options?: HTTPProbeFetchOptions
  ): Promise<HTTPProbeListResponse> {
    return this.fetchHTTPProbes(
      {
        ...params,
        asset_id: assetId,
      },
      options
    );
  }

  /**
   * Fetch HTTP probes for a specific scan job
   * 
   * Convenience method for scan job-specific queries.
   * 
   * @param scanJobId - Scan job UUID
   * @param params - Additional query parameters
   * @returns List of HTTP probes for the scan job
   */
  async fetchHTTPProbesByScanJob(
    scanJobId: string,
    params?: Omit<HTTPProbeQueryParams, 'scan_job_id'>,
    options?: HTTPProbeFetchOptions
  ): Promise<HTTPProbeListResponse> {
    return this.fetchHTTPProbes(
      {
        ...params,
        scan_job_id: scanJobId,
      },
      options
    );
  }

  /**
   * Clear cache for specific query or entire cache
   * 
   * @param params - Query parameters to clear (optional, clears all if not provided)
   */
  clearCache(params?: HTTPProbeQueryParams): void {
    if (params) {
      const cacheKey = this.getCacheKey(params);
      this.cache.delete(cacheKey);
    } else {
      this.cache.clear();
    }
  }

  /**
   * Get cache statistics (for debugging)
   */
  getCacheStats(): {
    size: number;
    entries: Array<{ key: string; age: number; valid: boolean }>;
  } {
    const entries = Array.from(this.cache.entries()).map(([key, entry]) => ({
      key,
      age: Date.now() - entry.timestamp,
      valid: this.isCacheValid(entry),
    }));

    return {
      size: this.cache.size,
      entries,
    };
  }
}

// ================================================================
// Export Service Instance
// ================================================================

export const httpProbesService = new HTTPProbesService();

// ================================================================
// Export Individual Functions (for convenience)
// ================================================================

export const fetchHTTPProbes = (params?: HTTPProbeQueryParams, options?: HTTPProbeFetchOptions) =>
  httpProbesService.fetchHTTPProbes(params, options);

export const fetchHTTPProbeById = (probeId: string) =>
  httpProbesService.fetchHTTPProbeById(probeId);

export const fetchHTTPProbeStats = (params?: { asset_id?: string; scan_job_id?: string }) =>
  httpProbesService.fetchHTTPProbeStats(params);

export const fetchHTTPProbesByAsset = (
  assetId: string,
  params?: Omit<HTTPProbeQueryParams, 'asset_id'>,
  options?: HTTPProbeFetchOptions
) => httpProbesService.fetchHTTPProbesByAsset(assetId, params, options);

export const fetchHTTPProbesByScanJob = (
  scanJobId: string,
  params?: Omit<HTTPProbeQueryParams, 'scan_job_id'>,
  options?: HTTPProbeFetchOptions
) => httpProbesService.fetchHTTPProbesByScanJob(scanJobId, params, options);

export const clearHTTPProbesCache = (params?: HTTPProbeQueryParams) =>
  httpProbesService.clearCache(params);
