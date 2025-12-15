import axios from 'axios';
import { API_BASE_URL } from './config';
import type {
  UnifiedScanRequest,
  UnifiedScanResponse,
  ScanStatusResponse,
  ListScansResponse,
} from '@/types/scans';

// Create axios instance with cookie-based auth (matching main API)
const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // SECURITY FIX: Enable cookie-based authentication
});

// Request interceptor - no longer needed for token injection since we use httpOnly cookies
// Cookies are automatically sent with each request
api.interceptors.request.use(
  (config) => {
    // No manual token handling - httpOnly cookies are sent automatically
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Don't automatically redirect on 401 errors - let the application handle authentication state
    // The AuthContext will manage authentication status and redirects appropriately
    return Promise.reject(error);
  }
);

// ================================================================
// Types and Interfaces
// ================================================================

export interface Asset {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  bug_bounty_url?: string;
  is_active: boolean;
  priority: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface AssetWithStats extends Asset {
  apex_domain_count: number;
  total_subdomains: number;
  active_domains: number;
  last_scan_date?: string;
  total_scans: number;
  completed_scans: number;
  failed_scans: number;
}

export interface AssetCreate {
  name: string;
  description?: string;
  bug_bounty_url?: string;
  priority?: number;
  tags?: string[];
}

// Alias for backward compatibility
export type AssetCreateRequest = AssetCreate;

export interface AssetUpdate {
  name?: string;
  description?: string;
  bug_bounty_url?: string;
  priority?: number;
  tags?: string[];
  is_active?: boolean;
}

// Alias for backward compatibility
export type AssetUpdateRequest = AssetUpdate;

export interface ApexDomain {
  id: string;
  asset_id: string;
  domain: string;
  description?: string;
  is_active: boolean;
  last_scanned_at?: string;
  registrar?: string;
  dns_servers?: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ApexDomainWithStats extends ApexDomain {
  total_scans?: number;
  completed_scans?: number;
  failed_scans?: number;
  running_scans?: number;
  total_subdomains?: number;
  asset_name?: string;  // For backward compatibility
  used_modules?: string[];  // For backward compatibility
  last_scan_date?: string;  // Alias for last_scanned_at
}

// For optimistic updates in UI
export interface ApexDomainOptimistic extends Partial<ApexDomainWithStats> {
  id: string;
  asset_id: string;
  domain: string;
  is_active: boolean;
}

// Legacy type alias for backward compatibility
export type Domain = ApexDomainWithStats;

export interface ApexDomainCreate {
  asset_id?: string;  // Optional since it's set from URL path
  domain: string;
  description?: string;
  is_active?: boolean;
}

// Alias for backward compatibility
export type ApexDomainCreateRequest = ApexDomainCreate;

// ================================================================
// Paginated Domain Response Types (Phase 2a)
// ================================================================

export interface PaginatedDomainsResponse {
  domains: ApexDomainWithStats[];
  pagination: {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
  filters: {
    is_active?: boolean;
    search?: string;
  };
  stats: {
    total_domains: number;
    filtered_count: number;
    load_time_ms: string;
  };
}

export interface PaginatedDomainsParams {
  page?: number;
  per_page?: number;
  is_active?: boolean;
  search?: string;
}

export interface ApexDomainUpdate {
  domain?: string;
  description?: string;
  is_active?: boolean;
  registrar?: string;
  dns_servers?: string[];
}

export interface AssetWithDomains {
  name: string;
  description?: string;
  bug_bounty_url?: string;
  priority?: number;
  domains: string[];
}

export interface UserAssetSummary {
  total_assets: number;
  active_assets: number;
  total_apex_domains: number;
  total_subdomains: number;
}

// ================================================================
// Asset Scan Job Types (NEW)
// ================================================================

export interface AssetScanJob {
  id: string;
  asset_id: string;
  asset_name: string;
  modules: string[];
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  total_domains: number;
  completed_domains: number;
  progress_percentage: number;
  active_domains_only: boolean;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  estimated_completion?: string;
  error_message?: string;
  total_subdomains_found: number;
  scan_type: 'asset_scan';
}

export interface AssetScanRequest {
  modules: string[];
  active_domains_only: boolean;
}

export interface AssetScanResponse {
  asset_scan_id: string;
  asset_id: string;
  asset_name: string;
  total_domains: number;
  active_domains: number;
  modules: string[];
  status: string;
  created_at: string;
  estimated_completion?: string;
}

export interface BulkAssetOperation {
  operation: 'scan' | 'delete';
  asset_ids: string[];
}

export interface AssetScanDetailedStatus {
  id: string;
  asset_id: string;
  asset_name: string;
  modules: string[];
  status: string;
  total_domains: number;
  completed_domains: number;
  failed_domains: number;
  running_domains: number;
  progress_percentage: number;
  active_domains_only: boolean;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  estimated_completion?: string;
  error_message?: string;
  metadata: Record<string, unknown>;
  total_subdomains_found: number;
  individual_scan_summary: {
    completed: number;
    failed: number;
    running: number;
    details: Array<{
      id: string;
      domain: string;
      status: string;
      result_count: number;
      completed_at?: string;
      error_message?: string;
    }>;
  };
}

export interface BulkOperationResult {
  operation: string;
  total_assets: number;
  successful: number;
  failed: number;
  results: Array<{
    asset_id: string;
    status: 'success' | 'failed';
    message?: string;
  }>;
}

export interface DomainUploadResult {
  total_lines: number;
  valid_domains: number;
  invalid_domains: number;
  duplicate_domains: number;
  added_domains: number;
  skipped_domains: number;
  domains_added: string[];
  invalid_lines: string[];
  duplicate_lines: string[];
}

// ================================================================
// NOTE: Old batch processing types removed (2025-11-11)
// Git history: git show HEAD~1:frontend/src/lib/api/assets.ts
// ================================================================

export interface AssetSubdomain {
  id: string;
  subdomain: string;
  ip_addresses: string[];
  status_code?: number;
  source_module: string;
  discovered_at: string;
  ssl_subject_cn?: string;
  cloud_provider?: string;
  parent_domain: string;
  scan_job_id: string;  // Required for tracking which scan found this subdomain
}

// Enhanced subdomain type with asset information (for optimized endpoint)
export interface AssetSubdomainWithAssetInfo extends AssetSubdomain {
  asset_id: string;
  asset_name: string;
  scan_job_domain: string;
  scan_job_type: string;
  scan_job_status: string;
  scan_job_created_at: string;
}

export interface AssetAnalytics {
  asset_id: string;
  asset_name: string;
  total_subdomains: number;
  module_effectiveness: Record<string, number>;
  cloud_provider_distribution: Record<string, number>;
  apex_domain_count: number;
  scan_success_rate: number;
}

// ================================================================
// API Error handling
// ================================================================

interface ApiRequestOptions {
  method?: string;
  body?: string;
  headers?: Record<string, string>;
}

async function apiRequest<T>(url: string, options: ApiRequestOptions = {}): Promise<T> {
  const response = await api.request({
    url,
    method: options.method || 'GET',
    data: options.body,
    headers: options.headers,
  });
  return response.data;
}

// ================================================================
// Asset API Class
// ================================================================

class AssetAPI {
  // ================================================================
  // Asset CRUD Operations
  // ================================================================

  async getAssets(): Promise<AssetWithStats[]> {
    return apiRequest<AssetWithStats[]>('/assets');
  }

  async getAsset(assetId: string): Promise<AssetWithStats> {
    return apiRequest<AssetWithStats>(`/assets/${assetId}`);
  }

  async createAsset(asset: AssetCreate): Promise<Asset> {
    return apiRequest<Asset>('/assets', {
      method: 'POST',
      body: JSON.stringify(asset),
    });
  }

  async updateAsset(assetId: string, updates: AssetUpdate): Promise<Asset> {
    return apiRequest<Asset>(`/assets/${assetId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async deleteAsset(assetId: string): Promise<{ message: string }> {
    return apiRequest<{ message: string }>(`/assets/${assetId}`, {
      method: 'DELETE',
    });
  }

  async createAssetWithDomains(assetData: AssetWithDomains): Promise<{ asset: Asset; domains: ApexDomain[] }> {
    return apiRequest<{ asset: Asset; domains: ApexDomain[] }>('/assets/with-domains', {
      method: 'POST',
      body: JSON.stringify(assetData),
    });
  }

  async getUserAssetSummary(): Promise<UserAssetSummary> {
    return apiRequest<UserAssetSummary>('/assets/summary');
  }

  // ================================================================
  // Apex Domain Management
  // ================================================================

  async getApexDomains(assetId: string): Promise<ApexDomainWithStats[]> {
    return apiRequest<ApexDomainWithStats[]>(`/assets/${assetId}/domains`);
  }

  // Alias for backward compatibility
  async getAssetDomains(assetId: string): Promise<ApexDomainWithStats[]> {
    return this.getApexDomains(assetId);
  }

  // ================================================================
  // NEW: Paginated Domain Management (Phase 2a)
  // ================================================================

  async getPaginatedAssetDomains(
    assetId: string, 
    params: PaginatedDomainsParams = {}
  ): Promise<PaginatedDomainsResponse> {
    const searchParams = new URLSearchParams();
    
    if (params.page) searchParams.set('page', params.page.toString());
    if (params.per_page) searchParams.set('per_page', params.per_page.toString());
    if (params.is_active !== undefined) searchParams.set('is_active', params.is_active.toString());
    if (params.search) searchParams.set('search', params.search);

    const url = `/assets/${assetId}/domains/paginated?${searchParams.toString()}`;
    
    return apiRequest<PaginatedDomainsResponse>(url, {
      method: 'GET',
    });
  }

  async createApexDomain(assetId: string, domain: ApexDomainCreate): Promise<ApexDomain> {
    return apiRequest<ApexDomain>(`/assets/${assetId}/domains`, {
      method: 'POST',
      body: JSON.stringify(domain),
    });
  }

  async updateApexDomain(assetId: string, domainId: string, updates: ApexDomainUpdate): Promise<ApexDomain> {
    return apiRequest<ApexDomain>(`/assets/${assetId}/domains/${domainId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async deleteApexDomain(assetId: string, domainId: string): Promise<{ message: string }> {
    return apiRequest<{ message: string }>(`/assets/${assetId}/domains/${domainId}`, {
      method: 'DELETE',
    });
  }

  async bulkUploadDomains(assetId: string, file: File): Promise<DomainUploadResult> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post(`/assets/${assetId}/domains/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  // ================================================================
  // NOTE: Old batch processing methods removed (2025-11-11)
  // Deleted: startEnhancedAssetScan, startMultiAssetBatchScan, 
  //          getBatchProgress, getBatchOptimizationAnalysis, startAssetScan
  // Use scansAPI instead for unified scan endpoint
  // Git history: git show HEAD~1:frontend/src/lib/api/assets.ts
  // ================================================================

  // ================================================================
  // Asset Scan Job Management (NEW)
  // ================================================================
  
  async listAssetScans(limit: number = 50): Promise<AssetScanJob[]> {
    return apiRequest<AssetScanJob[]>(`/assets/scans?limit=${limit}`);
  }

  async getAssetScanStatus(assetScanId: string): Promise<AssetScanDetailedStatus> {
    return apiRequest<AssetScanDetailedStatus>(`/assets/scan-jobs/${assetScanId}`);
  }

  async getAssetScanHistory(assetId: string, limit: number = 50): Promise<AssetScanJob[]> {
    return apiRequest<AssetScanJob[]>(`/assets/${assetId}/scan-history?limit=${limit}`);
  }

  // ================================================================
  // Bulk Operations
  // ================================================================

  async bulkOperation(operation: BulkAssetOperation): Promise<BulkOperationResult> {
    return apiRequest<BulkOperationResult>('/assets/bulk', {
      method: 'POST',
      body: JSON.stringify(operation),
    });
  }

  // ================================================================
  // Asset Analytics and Subdomains
  // ================================================================

  async getAssetSubdomains(assetId: string, options?: string | number): Promise<AssetSubdomain[]> {
    let url = `/assets/${assetId}/subdomains`;
    
    if (options) {
      if (typeof options === 'string') {
        // Module filter
        url += `?module=${options}`;
      } else {
        // Limit (backward compatibility)
        url += `?limit=${options}`;
      }
    }
    
    return apiRequest<AssetSubdomain[]>(url);
  }

  // ================================================================
  // Optimized Cross-Asset Subdomains (NEW)
  // ================================================================

  async getAllUserSubdomains(options?: {
    limit?: number;
    offset?: number;
    module?: string;
  }): Promise<AssetSubdomainWithAssetInfo[]> {
    let url = '/assets/subdomains/all';
    const params = new URLSearchParams();
    
    if (options?.limit) {
      params.append('limit', options.limit.toString());
    }
    if (options?.offset) {
      params.append('offset', options.offset.toString());
    }
    if (options?.module) {
      params.append('module', options.module);
    }
    
    if (params.toString()) {
      url += `?${params.toString()}`;
    }
    
    return apiRequest<AssetSubdomainWithAssetInfo[]>(url);
  }

  async getAssetAnalytics(assetId: string): Promise<AssetAnalytics> {
    return apiRequest<AssetAnalytics>(`/assets/${assetId}/analytics`);
  }
}

// ================================================================
// Unified Scans API (NEW - 2025-11-11)
// ================================================================

/**
 * ScansAPI - Unified scan endpoint management
 * 
 * Replaces old batch processing endpoints with a single, streamlined API:
 * - POST /api/v1/scans - Start a new scan
 * - GET /api/v1/scans/{scan_id} - Get scan status (for polling)
 * - GET /api/v1/scans - List all scans
 * 
 * All scans use the optimal 'subfinder + dnsx' streaming configuration.
 * 
 * @see /docs/refactoring/nov10_2025/unified_scan_refactoring_2025_11_10.md
 */
class ScansAPI {
  /**
   * Start a new unified scan for one or more assets.
   * 
   * Each asset's apex domains will be scanned using the streaming workflow:
   * Subfinder discovers subdomains → DNSx resolves them in real-time.
   * 
   * @param request - Scan request with asset IDs
   * @returns Scan response with scan_id for status tracking
   * 
   * @example
   * ```typescript
   * const response = await scansAPI.startScan({
   *   asset_ids: ['bcc2a92d-8c12-4fc2-8544-c2b2503e53b7']
   * });
   * console.log('Scan started:', response.scan_id);
   * ```
   */
  async startScan(request: UnifiedScanRequest): Promise<UnifiedScanResponse> {
    return apiRequest<UnifiedScanResponse>('/scans', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Get detailed status for a specific scan.
   * 
   * Use this for polling scan progress. Poll every 3-5 seconds while
   * status is 'pending' or 'running'.
   * 
   * @param scanId - Unique scan ID from startScan()
   * @returns Detailed scan status with progress and results
   * 
   * @example
   * ```typescript
   * const status = await scansAPI.getScanStatus(scanId);
   * if (status.status === 'completed') {
   *   console.log('Subdomains found:', status.results?.total_subdomains);
   * }
   * ```
   */
  async getScanStatus(scanId: string): Promise<ScanStatusResponse> {
    return apiRequest<ScanStatusResponse>(`/scans/${scanId}`);
  }

  /**
   * List all scans for the current user.
   * 
   * Optionally filter by status and limit for pagination.
   * 
   * @param options - Filter options (status, limit, offset)
   * @returns List of scan summaries
   * 
   * @example
   * ```typescript
   * // Get running scans
   * const running = await scansAPI.listScans({ status: 'running', limit: 1 });
   * 
   * // Get recent scans
   * const recent = await scansAPI.listScans({ limit: 20 });
   * ```
   */
  async listScans(options?: { 
    status?: 'pending' | 'running' | 'completed' | 'failed'; 
    limit?: number;
    offset?: number;
  }): Promise<ListScansResponse> {
    const params = new URLSearchParams();
    if (options?.status) params.append('status_filter', options.status);
    if (options?.limit) params.append('limit', options.limit.toString());
    if (options?.offset) params.append('offset', options.offset.toString());
    
    const queryString = params.toString();
    return apiRequest<ListScansResponse>(`/scans${queryString ? `?${queryString}` : ''}`);
  }

  /**
   * Convenience method to start a scan for a single asset.
   * 
   * Wrapper around startScan() for single-asset use cases.
   * 
   * @param assetId - Asset ID to scan
   * @param modules - Modules to run (default: ['subfinder', 'dnsx'])
   * @param activeDomainsOnly - Scan only active domains (default: true)
   * @returns Scan response with scan_id
   * 
   * @example
   * ```typescript
   * const response = await scansAPI.startSingleAssetScan(
   *   assetId,
   *   ['subfinder', 'dnsx'],
   *   true
   * );
   * // Poll status: scansAPI.getScanStatus(response.scan_id)
   * ```
   */
  async startSingleAssetScan(
    assetId: string,
    modules: string[] = ['subfinder', 'dnsx'],
    activeDomainsOnly: boolean = true
  ): Promise<UnifiedScanResponse> {
    return this.startScan({
      assets: {
        [assetId]: {
          modules,
          active_domains_only: activeDomainsOnly
        }
      }
    });
  }
}

// Export singleton instances
export const assetAPI = new AssetAPI();
export const scansAPI = new ScansAPI();

// Export default (assetAPI for backward compatibility)
export default assetAPI;
