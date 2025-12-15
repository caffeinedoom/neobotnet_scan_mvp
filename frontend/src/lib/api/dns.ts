import axios from 'axios';
import { apiClient } from './client';
import { API_ENDPOINTS } from './config';
import type {
  DNSRecord,
  DNSRecordListResponse,
  DNSQueryParams,
  SubdomainDNSInfo,
  DNSCacheEntry,
  DNSFetchOptions,
  DNSRecordType,
} from '@/types/dns';

// ================================================================
// DNS Service with Smart Caching
// ================================================================

/**
 * DNS Service Class
 * 
 * Provides DNS record fetching with intelligent caching to minimize
 * API calls and improve performance.
 * 
 * Cache Strategy:
 * - Per-asset caching with 5-minute TTL
 * - Parallel fetching for multiple assets
 * - Automatic cache invalidation on expiry
 */
class DNSService {
  private cache: Map<string, DNSCacheEntry> = new Map();
  private CACHE_TTL = 5 * 60 * 1000; // 5 minutes in milliseconds
  private pendingRequests: Map<string, Promise<DNSRecordListResponse>> = new Map();

  /**
   * Fetch DNS records for a specific asset
   * 
   * @param assetId - Asset UUID
   * @param params - Query parameters (pagination, filters)
   * @returns DNS record list with pagination metadata
   */
  async fetchDNSRecordsByAsset(
    assetId: string,
    params?: DNSQueryParams
  ): Promise<DNSRecordListResponse> {
    try {
      const endpoint = API_ENDPOINTS.DNS.RECORDS_BY_ASSET(assetId);
      
      // Build query string
      const queryParams = new URLSearchParams();
      if (params?.limit) queryParams.append('limit', params.limit.toString());
      if (params?.offset) queryParams.append('offset', params.offset.toString());
      if (params?.record_type) queryParams.append('record_type', params.record_type);
      if (params?.subdomain_name) queryParams.append('subdomain_name', params.subdomain_name);
      if (params?.scan_job_id) queryParams.append('scan_job_id', params.scan_job_id);
      if (params?.resolved_after) queryParams.append('resolved_after', params.resolved_after);
      if (params?.resolved_before) queryParams.append('resolved_before', params.resolved_before);

      const url = queryParams.toString() ? `${endpoint}?${queryParams}` : endpoint;

      // Check if there's already a pending request for this URL
      const requestKey = url;
      if (this.pendingRequests.has(requestKey)) {
        return this.pendingRequests.get(requestKey)!;
      }

      // Create the request promise
      const requestPromise = apiClient.get<DNSRecordListResponse>(url).then((response) => response.data);
      
      // Store it to prevent duplicate requests
      this.pendingRequests.set(requestKey, requestPromise);

      try {
        const data = await requestPromise;
        return data;
      } finally {
        // Clean up pending request
        this.pendingRequests.delete(requestKey);
      }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(
          error.response?.data?.detail || 
          error.response?.data?.error || 
          'Failed to fetch DNS records'
        );
      }
      throw error;
    }
  }

  /**
   * Fetch a single DNS record by ID
   * 
   * @param recordId - DNS record UUID
   * @returns Single DNS record
   */
  async fetchDNSRecordById(recordId: string): Promise<DNSRecord> {
    try {
      const endpoint = API_ENDPOINTS.DNS.RECORD_BY_ID(recordId);
      const response = await apiClient.get<DNSRecord>(endpoint);
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(
          error.response?.data?.detail || 
          error.response?.data?.error || 
          'Failed to fetch DNS record'
        );
      }
      throw error;
    }
  }

  /**
   * Aggregate DNS records by subdomain
   * 
   * Transforms flat DNS records into subdomain-grouped data for UI display.
   * 
   * @param records - Array of DNS records
   * @param includeFullRecords - Whether to include full records in aggregation
   * @returns Map of subdomain name to aggregated DNS info
   */
  aggregateDNSBySubdomain(
    records: DNSRecord[],
    includeFullRecords: boolean = false
  ): Map<string, SubdomainDNSInfo> {
    const aggregated = new Map<string, SubdomainDNSInfo>();

    for (const record of records) {
      const subdomain = record.subdomain;
      
      if (!aggregated.has(subdomain)) {
        aggregated.set(subdomain, {
          total_count: 0,
          ip_addresses: [],
          record_types: new Set<DNSRecordType>(),
          latest_resolved_at: record.resolved_at,
          records: [],
        });
      }

      const info = aggregated.get(subdomain)!;
      
      // Update count
      info.total_count++;

      // Add IP addresses (only for A and AAAA records)
      if ((record.record_type === 'A' || record.record_type === 'AAAA') && record.record_value) {
        if (!info.ip_addresses.includes(record.record_value)) {
          info.ip_addresses.push(record.record_value);
        }
      }

      // Add record type
      info.record_types.add(record.record_type);

      // Update latest resolved timestamp
      if (new Date(record.resolved_at) > new Date(info.latest_resolved_at)) {
        info.latest_resolved_at = record.resolved_at;
      }

      // Include full records if requested
      if (includeFullRecords) {
        info.records.push(record);
      }
    }

    return aggregated;
  }

  /**
   * Fetch DNS data for multiple assets with caching
   * 
   * This is the primary method for bulk-fetching DNS data for the subdomain list.
   * It handles caching, parallel fetching, and data aggregation.
   * 
   * @param assetIds - Array of asset UUIDs
   * @param options - Fetch options (force refresh, include records)
   * @returns Aggregated DNS data for all assets
   */
  async fetchDNSForAssets(
    assetIds: string[],
    options: DNSFetchOptions = {}
  ): Promise<Map<string, SubdomainDNSInfo>> {
    const { forceRefresh = false, includeRecords = false } = options;
    const allDNSData = new Map<string, SubdomainDNSInfo>();

    // Process assets in parallel
    await Promise.all(
      assetIds.map(async (assetId) => {
        try {
          // Check cache first (unless force refresh)
          if (!forceRefresh) {
            const cached = this.getCachedDNS(assetId);
            if (cached) {
              // Merge cached data into result
              cached.data.forEach((value, key) => {
                allDNSData.set(key, value);
              });
              return; // Skip API call
            }
          }

          // Fetch from API with high limit to get all records for caching
          const response = await this.fetchDNSRecordsByAsset(assetId, {
            limit: 1000, // Fetch up to 1000 records for caching
          });

          // Aggregate by subdomain
          const aggregated = this.aggregateDNSBySubdomain(
            response.dns_records,
            includeRecords
          );

          // Cache the aggregated data
          this.setCachedDNS(assetId, aggregated);

          // Merge into result
          aggregated.forEach((value, key) => {
            allDNSData.set(key, value);
          });

        } catch (error) {
          // Log error but continue with other assets
          console.error(`Failed to fetch DNS for asset ${assetId}:`, error);
          // Don't throw - allow other assets to load
        }
      })
    );

    return allDNSData;
  }

  /**
   * Get cached DNS data for an asset
   * 
   * @param assetId - Asset UUID
   * @returns Cached entry or null if expired/not found
   */
  private getCachedDNS(assetId: string): DNSCacheEntry | null {
    const cached = this.cache.get(assetId);
    if (!cached) return null;

    // Check if cache is expired
    const isExpired = Date.now() - cached.timestamp > this.CACHE_TTL;
    if (isExpired) {
      this.cache.delete(assetId);
      return null;
    }

    return cached;
  }

  /**
   * Set cached DNS data for an asset
   * 
   * @param assetId - Asset UUID
   * @param data - Aggregated DNS data
   */
  private setCachedDNS(assetId: string, data: Map<string, SubdomainDNSInfo>): void {
    this.cache.set(assetId, {
      data,
      timestamp: Date.now(),
      assetId,
    });
  }

  /**
   * Clear cache for a specific asset or all assets
   * 
   * @param assetId - Optional asset UUID (clears all if omitted)
   */
  clearCache(assetId?: string): void {
    if (assetId) {
      this.cache.delete(assetId);
    } else {
      this.cache.clear();
    }
  }

  /**
   * Get cache statistics (for debugging)
   */
  getCacheStats() {
    return {
      size: this.cache.size,
      entries: Array.from(this.cache.keys()),
      ttl: this.CACHE_TTL,
    };
  }
}

// ================================================================
// Export singleton instance
// ================================================================

export const dnsService = new DNSService();

// ================================================================
// Export helper functions for direct use
// ================================================================

/**
 * Fetch DNS records for a specific asset
 * 
 * @param assetId - Asset UUID
 * @param params - Query parameters
 */
export const fetchDNSRecordsByAsset = (
  assetId: string,
  params?: DNSQueryParams
): Promise<DNSRecordListResponse> => {
  return dnsService.fetchDNSRecordsByAsset(assetId, params);
};

/**
 * Fetch a single DNS record by ID
 * 
 * @param recordId - DNS record UUID
 */
export const fetchDNSRecordById = (recordId: string): Promise<DNSRecord> => {
  return dnsService.fetchDNSRecordById(recordId);
};

/**
 * Fetch DNS data for multiple assets (with caching)
 * 
 * Primary function for bulk-fetching DNS data.
 * 
 * @param assetIds - Array of asset UUIDs
 * @param options - Fetch options
 */
export const fetchDNSForAssets = (
  assetIds: string[],
  options?: DNSFetchOptions
): Promise<Map<string, SubdomainDNSInfo>> => {
  return dnsService.fetchDNSForAssets(assetIds, options);
};

/**
 * Clear DNS cache
 * 
 * @param assetId - Optional asset UUID (clears all if omitted)
 */
export const clearDNSCache = (assetId?: string): void => {
  dnsService.clearCache(assetId);
};

/**
 * Aggregate DNS records by subdomain
 * 
 * Utility function for client-side aggregation.
 * 
 * @param records - Array of DNS records
 * @param includeFullRecords - Whether to include full records
 */
export const aggregateDNSBySubdomain = (
  records: DNSRecord[],
  includeFullRecords?: boolean
): Map<string, SubdomainDNSInfo> => {
  return dnsService.aggregateDNSBySubdomain(records, includeFullRecords);
};
