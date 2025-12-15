import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchDNSForAssets } from '@/lib/api/dns';
import type { SubdomainDNSInfo, DNSFetchOptions } from '@/types/dns';

/**
 * Custom hook for fetching DNS data for multiple assets
 * 
 * This hook provides a clean interface for components to fetch DNS data
 * with automatic loading/error state management and caching support.
 * 
 * @example
 * ```tsx
 * const { dnsData, loading, error, refetch } = useDNSData(assetIds);
 * 
 * if (loading) return <Loader />;
 * if (error) return <Error message={error} />;
 * 
 * const dnsInfo = dnsData.get(subdomain.subdomain);
 * ```
 */
export function useDNSData(
  assetIds: string[],
  options: DNSFetchOptions = {}
) {
  const [dnsData, setDnsData] = useState<Map<string, SubdomainDNSInfo>>(new Map());
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Destructure options for stable dependencies
  const { forceRefresh = false, includeRecords = false } = options;

  // Track previous asset IDs to prevent unnecessary refetches
  const prevAssetIdsRef = useRef<string>('');
  
  // Create stable key from sorted asset IDs (computed directly, not memoized)
  const currentAssetIdsKey = assetIds.length > 0 ? [...assetIds].sort().join(',') : '';

  /**
   * Fetch DNS data for the provided asset IDs
   */
  const fetchData = useCallback(async () => {
    // Don't fetch if no asset IDs provided
    if (!assetIds || assetIds.length === 0) {
      setDnsData(new Map());
      prevAssetIdsRef.current = '';
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await fetchDNSForAssets(assetIds, { forceRefresh, includeRecords });
      setDnsData(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load DNS data';
      setError(errorMessage);
      console.error('Error fetching DNS data:', err);
    } finally {
      setLoading(false);
    }
  }, [assetIds, forceRefresh, includeRecords]);

  /**
   * Refetch DNS data (useful for retry button)
   */
  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  /**
   * Auto-fetch when asset IDs actually change (not just array reference)
   */
  useEffect(() => {
    // Only fetch if asset IDs have actually changed
    if (currentAssetIdsKey !== prevAssetIdsRef.current) {
      prevAssetIdsRef.current = currentAssetIdsKey;
      fetchData();
    }
  }, [currentAssetIdsKey, fetchData]);

  return {
    dnsData,
    loading,
    error,
    refetch,
  };
}

/**
 * Hook for extracting unique asset IDs from subdomain data
 * 
 * Helper hook to extract asset IDs from subdomain array for use with useDNSData.
 * Uses a ref to track previous values and only returns a new array when
 * the actual asset IDs change, preventing infinite re-render loops.
 * 
 * @example
 * ```tsx
 * const assetIds = useAssetIdsFromSubdomains(subdomains);
 * const { dnsData } = useDNSData(assetIds);
 * ```
 */
export function useAssetIdsFromSubdomains<T extends { asset_id: string }>(
  subdomains: T[]
): string[] {
  const [assetIds, setAssetIds] = useState<string[]>([]);
  const prevKeyRef = useRef<string>('');

  useEffect(() => {
    if (!subdomains || subdomains.length === 0) {
      const emptyKey = '';
      if (prevKeyRef.current !== emptyKey) {
        prevKeyRef.current = emptyKey;
        setAssetIds([]);
      }
      return;
    }

    // Create stable key from sorted unique asset IDs
    const uniqueIds = [...new Set(subdomains.map((s) => s.asset_id))];
    const currentKey = uniqueIds.sort().join(',');

    // Only update if asset IDs have actually changed
    if (currentKey !== prevKeyRef.current) {
      prevKeyRef.current = currentKey;
      setAssetIds(uniqueIds);
    }
  }, [subdomains]);

  return assetIds;
}
