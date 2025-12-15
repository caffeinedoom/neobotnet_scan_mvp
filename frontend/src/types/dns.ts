// DNS types that match the backend Pydantic schemas (backend/app/schemas/dns.py)

/**
 * DNS Record Type
 * 
 * Represents a single DNS record from the database.
 * Matches the backend DNSRecord schema exactly.
 */
export interface DNSRecord {
  id: string;                    // UUID
  subdomain: string;              // Full subdomain (e.g., "api.epicgames.com")
  parent_domain: string;          // Parent domain (e.g., "epicgames.com")
  record_type: DNSRecordType;     // Type of DNS record
  record_value: string;           // DNS resolution value (IP, CNAME, etc.)
  resolved_at: string;            // ISO timestamp (e.g., "2025-11-02T22:58:39Z")
  scan_job_id: string | null;     // UUID of the scan job (nullable)
  batch_scan_id: string | null;   // UUID of the batch scan (nullable)
  asset_id: string;               // UUID of the asset
  created_at: string;             // ISO timestamp
  updated_at: string;             // ISO timestamp
}

/**
 * DNS Record Types
 * 
 * Supported DNS record types from DNSX scanner.
 */
export type DNSRecordType = 'A' | 'AAAA' | 'CNAME' | 'MX' | 'NS' | 'TXT' | 'SOA' | 'PTR';

/**
 * DNS Record List Response
 * 
 * Response from GET /api/v1/assets/{asset_id}/dns-records
 * Includes pagination metadata and optional warnings.
 */
export interface DNSRecordListResponse {
  dns_records: DNSRecord[];
  total_count: number;
  limit: number;
  offset: number;
  warning?: string;              // Optional warning for large result sets
}

/**
 * DNS Query Parameters
 * 
 * Query parameters for fetching DNS records with filters and pagination.
 */
export interface DNSQueryParams {
  // Pagination
  limit?: number;                 // Default: 50, Max: 1000
  offset?: number;                // Default: 0
  
  // Filters
  record_type?: DNSRecordType;    // Filter by record type
  subdomain_name?: string;        // Filter by subdomain name (exact match)
  scan_job_id?: string;           // Filter by scan job ID
  
  // Date range filters
  resolved_after?: string;        // ISO timestamp (e.g., "2025-11-01T00:00:00Z")
  resolved_before?: string;       // ISO timestamp
}

/**
 * Subdomain DNS Info (Aggregated)
 * 
 * Client-side aggregated DNS data for a single subdomain.
 * Used to display DNS information in subdomain cards.
 */
export interface SubdomainDNSInfo {
  total_count: number;            // Total DNS records for this subdomain
  ip_addresses: string[];         // Unique IP addresses (A and AAAA records)
  record_types: Set<DNSRecordType>; // Unique record types
  latest_resolved_at: string;     // Most recent resolution timestamp
  records: DNSRecord[];           // Full DNS records (optional, for details)
}

/**
 * DNS Cache Entry
 * 
 * Internal cache structure for storing DNS data with TTL.
 */
export interface DNSCacheEntry {
  data: Map<string, SubdomainDNSInfo>;  // Subdomain name -> DNS info
  timestamp: number;                     // Cache creation time (Date.now())
  assetId: string;                       // Asset ID for this cache entry
}

/**
 * DNS Fetch Options
 * 
 * Options for fetching DNS data with cache control.
 */
export interface DNSFetchOptions {
  forceRefresh?: boolean;         // Bypass cache and fetch fresh data
  includeRecords?: boolean;       // Include full DNS records in aggregation
}

/**
 * DNS Error Response
 * 
 * Standard error response for DNS API calls.
 */
export interface DNSErrorResponse {
  detail: string;
  error?: string;
}
