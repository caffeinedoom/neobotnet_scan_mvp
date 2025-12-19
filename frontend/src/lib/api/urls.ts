/**
 * URLs API Client
 * 
 * API functions for fetching URL data from the urls table.
 */

import { createClient } from '@/lib/supabase/client';
import type { URLRecord, URLStats, URLQueryParams } from '@/types/urls';

/**
 * Fetch URLs with filtering and pagination
 */
export async function fetchURLs(params: URLQueryParams = {}): Promise<URLRecord[]> {
  const supabase = createClient();
  
  let query = supabase
    .from('urls')
    .select('*')
    .order('first_discovered_at', { ascending: false });
  
  // Apply filters
  if (params.asset_id) {
    query = query.eq('asset_id', params.asset_id);
  }
  
  if (params.is_alive !== undefined) {
    query = query.eq('is_alive', params.is_alive);
  }
  
  if (params.status_code) {
    query = query.eq('status_code', params.status_code);
  }
  
  if (params.source) {
    query = query.contains('sources', [params.source]);
  }
  
  if (params.has_params !== undefined) {
    query = query.eq('has_params', params.has_params);
  }
  
  if (params.file_extension) {
    query = query.eq('file_extension', params.file_extension);
  }
  
  if (params.search) {
    query = query.or(
      `url.ilike.%${params.search}%,domain.ilike.%${params.search}%,title.ilike.%${params.search}%`
    );
  }
  
  // Apply pagination
  if (params.limit) {
    query = query.limit(params.limit);
  }
  
  if (params.offset) {
    query = query.range(params.offset, params.offset + (params.limit || 100) - 1);
  }
  
  const { data, error } = await query;
  
  if (error) {
    console.error('Error fetching URLs:', error);
    throw error;
  }
  
  return data || [];
}

/**
 * Fetch URL statistics
 */
export async function fetchURLStats(params: { asset_id?: string } = {}): Promise<URLStats> {
  const supabase = createClient();
  
  // Base query for counting
  let baseQuery = supabase.from('urls').select('*', { count: 'exact', head: true });
  
  if (params.asset_id) {
    baseQuery = baseQuery.eq('asset_id', params.asset_id);
  }
  
  // Get total count
  const { count: totalUrls } = await baseQuery;
  
  // Get alive count
  let aliveQuery = supabase.from('urls').select('*', { count: 'exact', head: true }).eq('is_alive', true);
  if (params.asset_id) aliveQuery = aliveQuery.eq('asset_id', params.asset_id);
  const { count: aliveUrls } = await aliveQuery;
  
  // Get dead count
  let deadQuery = supabase.from('urls').select('*', { count: 'exact', head: true }).eq('is_alive', false);
  if (params.asset_id) deadQuery = deadQuery.eq('asset_id', params.asset_id);
  const { count: deadUrls } = await deadQuery;
  
  // Get pending count (not yet resolved)
  let pendingQuery = supabase.from('urls').select('*', { count: 'exact', head: true }).is('resolved_at', null);
  if (params.asset_id) pendingQuery = pendingQuery.eq('asset_id', params.asset_id);
  const { count: pendingUrls } = await pendingQuery;
  
  // Get URLs with params count
  let paramsQuery = supabase.from('urls').select('*', { count: 'exact', head: true }).eq('has_params', true);
  if (params.asset_id) paramsQuery = paramsQuery.eq('asset_id', params.asset_id);
  const { count: urlsWithParams } = await paramsQuery;
  
  // Get unique domains (requires fetching distinct domains)
  let domainsQuery = supabase.from('urls').select('domain');
  if (params.asset_id) domainsQuery = domainsQuery.eq('asset_id', params.asset_id);
  const { data: domainsData } = await domainsQuery;
  const uniqueDomains = new Set(domainsData?.map(d => d.domain) || []).size;
  
  // For top sources, status codes, technologies, and file extensions, we'll use the data we fetch
  // In a production system, this would be aggregated server-side via RPC or Edge Function
  
  return {
    total_urls: totalUrls || 0,
    alive_urls: aliveUrls || 0,
    dead_urls: deadUrls || 0,
    pending_urls: pendingUrls || 0,
    urls_with_params: urlsWithParams || 0,
    unique_domains: uniqueDomains,
    top_sources: [],  // Would need aggregation query
    top_status_codes: [],  // Would need aggregation query
    top_technologies: [],  // Would need aggregation query
    top_file_extensions: [],  // Would need aggregation query
  };
}

/**
 * Fetch a single URL by ID
 */
export async function fetchURLById(id: string): Promise<URLRecord | null> {
  const supabase = createClient();
  
  const { data, error } = await supabase
    .from('urls')
    .select('*')
    .eq('id', id)
    .single();
  
  if (error) {
    console.error('Error fetching URL:', error);
    throw error;
  }
  
  return data;
}

