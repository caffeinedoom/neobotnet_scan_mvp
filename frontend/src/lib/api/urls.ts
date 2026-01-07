/**
 * URLs API Client
 * 
 * API functions for fetching URL data through the backend API.
 * Properly authenticated through the API client (not direct Supabase).
 */

import { apiClient } from '@/lib/api/client';
import type { URLRecord, URLStats, URLQueryParams } from '@/types/urls';

/**
 * Response structure from the /api/v1/urls endpoint
 */
interface URLsApiResponse {
  urls: URLRecord[];
  total: number;
  limit: number;
  offset: number;
  quota: {
    plan_type: string;
    urls_limit: number;
    urls_viewed: number;
    urls_remaining: number;
    is_limited: boolean;
    upgrade_required: boolean;
  };
}

/**
 * Fetch URLs with filtering and pagination via backend API
 * Returns URLs, total count, and quota information
 */
export async function fetchURLs(params: URLQueryParams = {}): Promise<{ urls: URLRecord[]; total: number; quota: URLsApiResponse['quota'] }> {
  const queryParams = new URLSearchParams();
  
  if (params.asset_id) queryParams.append('asset_id', params.asset_id);
  if (params.parent_domain) queryParams.append('parent_domain', params.parent_domain);
  if (params.is_alive !== undefined) queryParams.append('is_alive', String(params.is_alive));
  if (params.status_code) queryParams.append('status_code', String(params.status_code));
  if (params.has_params !== undefined) queryParams.append('has_params', String(params.has_params));
  if (params.file_extension) queryParams.append('file_extension', params.file_extension);
  if (params.search) queryParams.append('search', params.search);
  if (params.limit) queryParams.append('limit', String(params.limit));
  if (params.offset) queryParams.append('offset', String(params.offset));
  
  const queryString = queryParams.toString();
  const endpoint = `/api/v1/urls${queryString ? `?${queryString}` : ''}`;
  
  const response = await apiClient.get<URLsApiResponse>(endpoint);
  return {
    urls: response.data.urls || [],
    total: response.data.total || 0,
    quota: response.data.quota
  };
}

/**
 * Fetch URL statistics via backend API
 */
export async function fetchURLStats(params: { asset_id?: string } = {}): Promise<URLStats> {
  const queryParams = new URLSearchParams();
  
  if (params.asset_id) queryParams.append('asset_id', params.asset_id);
  
  const queryString = queryParams.toString();
  const endpoint = `/api/v1/urls/stats${queryString ? `?${queryString}` : ''}`;
  
  const response = await apiClient.get<URLStats>(endpoint);
  return response.data;
}

/**
 * Fetch a single URL by ID via backend API
 */
export async function fetchURLById(id: string): Promise<URLRecord | null> {
  try {
    const response = await apiClient.get<URLRecord>(`/api/v1/urls/${id}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching URL:', error);
    return null;
  }
}
