// HTTP Probes types that match the backend Pydantic schemas (backend/app/schemas/http_probes.py)

/**
 * HTTP Probe Record
 * 
 * Represents a single HTTP probe result from the database.
 * Matches the backend HTTPProbeResponse schema exactly.
 */
export interface HTTPProbe {
  id: string;                       // UUID
  scan_job_id: string;              // UUID of the scan job
  asset_id: string;                 // UUID of the asset
  url: string;                      // Full URL (e.g., "https://api.example.com")
  subdomain: string;                // Subdomain or IP (e.g., "api.example.com")
  parent_domain: string;            // Parent domain (e.g., "example.com")
  scheme: string;                   // "http" or "https"
  port: number;                     // Port number (e.g., 443, 80)
  status_code: number | null;       // HTTP status code (e.g., 200, 404)
  title: string | null;             // Page title
  webserver: string | null;         // Web server header (e.g., "nginx/1.18.0")
  content_length: number | null;    // Response content length in bytes
  content_type: string | null;      // Content-Type header (e.g., "text/html")
  final_url: string | null;         // Final URL after redirects
  ip: string | null;                // Resolved IP address
  technologies: string[];           // Detected technologies (e.g., ["React", "Webpack"])
  cdn_name: string | null;          // CDN provider if detected
  asn: string | null;               // Autonomous System Number
  chain_status_codes: number[];     // HTTP status codes in redirect chain
  location: string | null;          // Location header from redirects
  favicon_md5: string | null;       // MD5 hash of favicon
  created_at: string;               // ISO timestamp (e.g., "2025-11-16T17:33:03Z")
}

/**
 * HTTP Probe Statistics Response
 * 
 * Aggregate statistics for HTTP probes.
 * Returned by GET /api/v1/http-probes/stats/summary
 */
export interface HTTPProbeStats {
  total_probes: number;                           // Total number of probes
  status_code_distribution: Record<number, number>; // { 200: 13, 404: 4 }
  top_technologies: TechnologyCount[];            // Top detected technologies
  top_servers: ServerCount[];                     // Top web servers
  cdn_usage: Record<string, number>;              // CDN distribution
  redirect_chains_count: number;                  // Number of probes with redirects
}

/**
 * Technology Count
 * 
 * Used in top technologies list
 */
export interface TechnologyCount {
  name: string;   // Technology name (e.g., "React")
  count: number;  // Number of occurrences
}

/**
 * Server Count
 * 
 * Used in top servers list
 */
export interface ServerCount {
  name: string;   // Server name (e.g., "nginx/1.18.0")
  count: number;  // Number of occurrences
}

/**
 * HTTP Probe Query Parameters
 * 
 * Query parameters for fetching HTTP probes with filters and pagination.
 */
export interface HTTPProbeQueryParams {
  // Pagination
  limit?: number;                 // Default: 100, Max: 1000
  offset?: number;                // Default: 0
  
  // Filters
  asset_id?: string;              // Filter by asset UUID
  scan_job_id?: string;           // Filter by scan job UUID
  status_code?: number;           // Filter by HTTP status code
  scheme?: 'http' | 'https';      // Filter by scheme
  technology?: string;            // Filter by technology (e.g., "React")
  has_redirect?: boolean;         // Filter probes with redirect chains
  cdn_name?: string;              // Filter by CDN provider
}

/**
 * HTTP Probe List Response
 * 
 * Response from GET /api/v1/http-probes
 */
export type HTTPProbeListResponse = HTTPProbe[];

/**
 * HTTP Probe Cache Entry
 * 
 * Client-side cache entry for HTTP probes with TTL.
 */
export interface HTTPProbeCacheEntry {
  data: HTTPProbeListResponse;
  timestamp: number;              // Unix timestamp in milliseconds
  params: HTTPProbeQueryParams;   // Query params used for this cache entry
}

/**
 * HTTP Probe Fetch Options
 * 
 * Options for fetching HTTP probes with caching control.
 */
export interface HTTPProbeFetchOptions {
  forceRefresh?: boolean;         // Bypass cache
  signal?: AbortSignal;           // For request cancellation
}

/**
 * Status Code Categories
 * 
 * Helper for categorizing HTTP status codes by type.
 */
export const STATUS_CODE_CATEGORIES = {
  SUCCESS: [200, 201, 202, 203, 204],
  REDIRECT: [301, 302, 303, 307, 308],
  CLIENT_ERROR: [400, 401, 403, 404, 405, 429],
  SERVER_ERROR: [500, 502, 503, 504],
};

/**
 * Status Code Category Type
 */
export type StatusCodeCategory = keyof typeof STATUS_CODE_CATEGORIES;

/**
 * Helper function to get status code category
 */
export function getStatusCodeCategory(statusCode: number): StatusCodeCategory | null {
  if (STATUS_CODE_CATEGORIES.SUCCESS.includes(statusCode)) return 'SUCCESS';
  if (STATUS_CODE_CATEGORIES.REDIRECT.includes(statusCode)) return 'REDIRECT';
  if (STATUS_CODE_CATEGORIES.CLIENT_ERROR.includes(statusCode)) return 'CLIENT_ERROR';
  if (STATUS_CODE_CATEGORIES.SERVER_ERROR.includes(statusCode)) return 'SERVER_ERROR';
  return null;
}

/**
 * Helper function to check if probe has redirect chain
 */
export function hasRedirectChain(probe: HTTPProbe): boolean {
  return probe.chain_status_codes.length > 0;
}

/**
 * Helper function to check if probe is successful (2xx status)
 */
export function isSuccessfulProbe(probe: HTTPProbe): boolean {
  return probe.status_code !== null && probe.status_code >= 200 && probe.status_code < 300;
}
