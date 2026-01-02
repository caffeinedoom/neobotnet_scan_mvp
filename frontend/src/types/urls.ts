/**
 * URL Resolver Types
 * 
 * Types for the urls table managed by the url-resolver module.
 * URLs are discovered by Katana, Waymore, GAU, etc. and probed/enriched by url-resolver.
 */

export interface URLRecord {
  id: string;
  asset_id: string;
  scan_job_id: string | null;
  
  // Core URL data
  url: string;
  url_hash: string;
  domain: string;
  path: string;
  query_params: Record<string, string> | null;
  
  // Discovery tracking (sources not exposed via API)
  first_discovered_at: string;
  
  // Resolution metadata
  resolved_at: string | null;
  is_alive: boolean | null;
  status_code: number | null;
  content_type: string | null;
  content_length: number | null;
  response_time_ms: number | null;
  
  // Enrichment data
  title: string | null;
  final_url: string | null;
  redirect_chain: string[] | null;
  webserver: string | null;
  technologies: string[] | null;
  
  // Classification
  has_params: boolean;
  file_extension: string | null;
  
  // Timestamps
  created_at: string;
  updated_at: string;
}

export interface URLStats {
  total_urls: number;
  alive_urls: number;
  dead_urls: number;
  pending_urls: number;
  urls_with_params: number;
  unique_domains: number;
  top_status_codes: { status_code: number; count: number }[];
  top_technologies: { name: string; count: number }[];
  top_file_extensions: { extension: string; count: number }[];
}

export interface URLQueryParams {
  limit?: number;
  offset?: number;
  asset_id?: string;
  is_alive?: boolean;
  status_code?: number;
  has_params?: boolean;
  file_extension?: string;
  search?: string;
}

