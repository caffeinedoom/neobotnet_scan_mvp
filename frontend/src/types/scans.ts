/**
 * Unified Scan Types
 * 
 * Types for the new unified scan endpoint (POST /api/v1/scans)
 * which replaces the old batch processing endpoints.
 * 
 * @see docs/refactoring/nov10_2025/unified_scan_refactoring_2025_11_10.md
 */

// ================================================================
// Request Types
// ================================================================

/**
 * Scan configuration for a single asset
 */
export interface AssetScanConfig {
  /** Modules to run for this asset */
  modules: string[];
  
  /** Whether to scan only active domains (default: true) */
  active_domains_only: boolean;
}

/**
 * Request body for starting a unified scan.
 * 
 * @example
 * ```typescript
 * const request: UnifiedScanRequest = {
 *   assets: {
 *     "asset-uuid-1": {
 *       modules: ["subfinder", "dnsx"],
 *       active_domains_only: true
 *     }
 *   }
 * };
 * ```
 */
export interface UnifiedScanRequest {
  /** 
   * Dictionary mapping asset IDs to scan configurations.
   * Key: asset UUID
   * Value: scan configuration (modules, options)
   */
  assets: Record<string, AssetScanConfig>;
}

// ================================================================
// Response Types
// ================================================================

/**
 * Response from starting a unified scan.
 * 
 * @example
 * ```json
 * {
 *   "scan_id": "550e8400-e29b-41d4-a716-446655440000",
 *   "asset_ids": ["bcc2a92d-8c12-4fc2-8544-c2b2503e53b7"],
 *   "status": "pending",
 *   "modules": ["subfinder", "dnsx"],
 *   "created_at": "2025-11-11T20:00:00Z"
 * }
 * ```
 */
export interface UnifiedScanResponse {
  /** Unique scan ID for tracking */
  scan_id: string;
  
  /** Asset IDs included in this scan */
  asset_ids: string[];
  
  /** Current scan status */
  status: ScanStatus;
  
  /** Modules being executed (currently always ['subfinder', 'dnsx']) */
  modules: string[];
  
  /** Timestamp when scan was created (ISO 8601) */
  created_at: string;
  
  /** Optional: Estimated completion time (if available) */
  estimated_completion?: string;
}

/**
 * Detailed scan status response from GET /api/v1/scans/{scan_id}
 * 
 * Used for polling scan progress.
 */
export interface ScanStatusResponse {
  /** Unique scan ID */
  scan_id: string;
  
  /** Asset IDs included in this scan */
  asset_ids: string[];
  
  /** Current scan status */
  status: ScanStatus;
  
  /** Modules being executed */
  modules: string[];
  
  /** Timestamp when scan was created (ISO 8601) */
  created_at: string;
  
  /** Timestamp when scan started (ISO 8601) */
  started_at?: string;
  
  /** Timestamp when scan completed (ISO 8601) */
  completed_at?: string;
  
  /** Progress information */
  progress?: {
    /** Number of apex domains processed */
    completed_domains: number;
    
    /** Total apex domains to process */
    total_domains: number;
    
    /** Completion percentage (0-100) */
    percentage: number;
    
    /** Estimated completion time (ISO 8601) */
    estimated_completion?: string;
  };
  
  /** Results summary (available when completed) */
  results?: {
    /** Total subdomains discovered */
    total_subdomains: number;
    
    /** Total DNS records resolved */
    total_dns_records: number;
    
    /** Breakdown by apex domain */
    by_apex_domain?: Record<string, {
      subdomains_found: number;
      dns_records_resolved: number;
    }>;
  };
  
  /** Error message (if status is 'failed') */
  error_message?: string;
  
  /** ECS task information (for debugging) */
  ecs_tasks?: Array<{
    task_arn: string;
    module: string;
    status: string;
    started_at?: string;
    stopped_at?: string;
  }>;
}

/**
 * Scan status enum
 */
export type ScanStatus = 
  | 'pending'     // Scan created, waiting to start
  | 'running'     // Scan in progress
  | 'completed'   // Scan finished successfully
  | 'failed'      // Scan encountered an error
  | 'cancelled';  // Scan was cancelled by user

// ================================================================
// List Scans Types
// ================================================================

/**
 * Response from GET /api/v1/scans (list all scans)
 */
export interface ListScansResponse {
  /** Array of scan summaries */
  scans: ScanSummary[];
  
  /** Pagination info (if implemented) */
  pagination?: {
    total: number;
    page: number;
    per_page: number;
    has_next: boolean;
  };
}

/**
 * Summary of a scan (used in list view)
 */
export interface ScanSummary {
  scan_id: string;
  asset_ids: string[];
  status: ScanStatus;
  modules: string[];
  created_at: string;
  completed_at?: string;
  total_subdomains?: number;
}

// ================================================================
// Module Presets (FUTURE ENHANCEMENT - Commented Out)
// ================================================================

/**
 * FUTURE: Module presets for simplified UX
 * Currently not used - all scans use 'subfinder + dnsx'
 * 
 * Uncomment when ready to implement module selection UI.
 */

// export type ModulePreset = 'quick' | 'complete' | 'advanced';

// export interface ModulePresetConfig {
//   preset: ModulePreset;
//   modules: string[];
//   description: string;
//   estimatedDuration: string;
// }

// export const MODULE_PRESETS: Record<ModulePreset, ModulePresetConfig> = {
//   quick: {
//     preset: 'quick',
//     modules: ['subfinder', 'dnsx'],
//     description: 'Fast subdomain discovery with DNS resolution (streaming)',
//     estimatedDuration: '5-10 min'
//   },
//   complete: {
//     preset: 'complete',
//     modules: ['subfinder', 'dnsx', 'httpx'],
//     description: 'Full reconnaissance with HTTP probing',
//     estimatedDuration: '15-30 min'
//   },
//   advanced: {
//     preset: 'advanced',
//     modules: ['subfinder', 'dnsx', 'httpx', 'nmap'],
//     description: 'Deep scan with port scanning',
//     estimatedDuration: '30-60 min'
//   }
// };
