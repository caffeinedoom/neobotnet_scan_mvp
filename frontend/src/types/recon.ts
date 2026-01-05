// Reconnaissance types that match the backend Pydantic schemas

export interface SubdomainScanRequest {
  domain: string;
  modules?: ReconModule[];
}

/**
 * Available reconnaissance modules.
 * 
 * CLEANUP NOTE (2025-10-06):
 * - Removed CLOUD_SSL (not implemented, won't be for a while)
 * - Future modules commented out until backend implementation
 */
export enum ReconModule {
  SUBFINDER = "subfinder",
  // Future modules (uncomment when backend implements them):
  // DNS_BRUTEFORCE = "dns_bruteforce",
  // HTTP_PROBE = "http_probe",
  // PORT_SCAN = "port_scan"
}

export interface ScanJob {
  id: string;
  user_id: string;
  domain: string;
  scan_type: string;
  modules?: string[];
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  completed_at?: string;
  result_count: number;
  error_message?: string;
  metadata: Record<string, unknown>;
  message?: string;
}

export interface ScanJobWithResults extends ScanJob {
  subdomains: string[] | EnhancedSubdomain[];  // Support both formats
  total_subdomains: number;
}

export interface EnhancedSubdomain {
  id: string;
  subdomain: string;
  ip_addresses?: string[];
  status_code?: number;
  response_size?: number;
  technologies?: string[];
  discovered_at: string;
  last_checked?: string;
  scan_job_id: string;
  
  // Cloud/Network Attribution (source_module removed for production)
  source_ip_range?: string;
  cloud_provider?: string;
  discovery_method?: string;
  
  // SSL Certificate Information
  ssl_subject_cn?: string;
  ssl_issuer?: string;
  ssl_valid_from?: string;
  ssl_valid_until?: string;
  ssl_serial_number?: string;
  ssl_is_wildcard?: boolean;
  ssl_is_valid?: boolean;
  ssl_is_expired?: boolean;
  ssl_days_until_expiry?: number;
}

export interface SubdomainResult {
  subdomain: string;
  ip_addresses: string[];
  discovered_at: string;
  scan_job_id: string;
  metadata?: Record<string, unknown>;
}

export interface ScanResponse {
  job_id: string;
  domain: string;
  modules?: string[];
  status: string;
  message: string;
}

export interface ScanProgress {
  job_id: string;
  domain: string;
  status: string;
  created_at: string;
  progress: {
    current_phase: string;
    progress_percent: number;
    total_results: number;
    filtered_results: number;
    database_writes: number;
    database_failures: number;
    db_success_rate: number;
    memory_usage_mb: number;
    total_errors: number;
    active_workers?: number;
    stored_batches?: number;
    estimated_eta?: string;
  };
}

export interface UserStats {
  total_scans: number;
  completed_scans: number;
  failed_scans: number;
  pending_scans: number;
  total_subdomains: number;
  avg_scan_duration?: number;
}
