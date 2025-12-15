import axios from 'axios';
import { API_BASE_URL, API_ENDPOINTS } from './config';

// Create axios instance with cookie-based auth
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Enable cookie-based authentication
});

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

// ================================================================
// Types and Interfaces  
// ================================================================

export interface DashboardStatistics {
  total_assets: number;
  active_assets: number;
  total_domains: number;
  active_domains: number;
  total_scans: number;
  completed_scans: number;
  failed_scans: number;
  pending_scans: number;
  total_subdomains: number;
  last_scan_date?: string;
}

export interface UsageOverview {
  current_assets: number;
  current_domains: number;
  current_active_scans: number;
  current_subdomains: number;
  scans_today: number;
  scans_this_month: number;
  max_assets: number;
  max_domains_per_asset: number;
  max_scans_per_day: number;
  max_scans_per_month: number;
  max_concurrent_scans: number;
  max_subdomains_stored: number;
  asset_limit_reached: boolean;
  daily_limit_reached: boolean;
  monthly_limit_reached: boolean;
  concurrent_limit_reached: boolean;
  storage_limit_reached: boolean;
}

export interface QuotaLimits {
  max_assets: number;
  max_domains_per_asset: number;
  max_scans_per_day: number;
  max_scans_per_month: number;
  max_concurrent_scans: number;
  max_subdomains_stored: number;
}

// ================================================================
// Usage API Class
// ================================================================

class UsageAPI {
  
  /**
   * Get optimized dashboard statistics in a single API call.
   * 
   * This replaces the previous approach of multiple API calls + client-side aggregation
   * with a single optimized database query.
   * 
   * Performance benefits:
   * - Reduces 2+ API calls to 1
   * - Eliminates client-side data processing
   * - Uses database-level aggregation
   * - Scales O(1) instead of O(n²)
   */
  async getDashboardStatistics(): Promise<DashboardStatistics> {
    const response = await api.get(API_ENDPOINTS.USAGE.DASHBOARD_STATS);
    return response.data;
  }

  async getUsageOverview(): Promise<UsageOverview> {
    const response = await api.get(API_ENDPOINTS.USAGE.OVERVIEW);
    return response.data;
  }

  async getQuotaLimits(): Promise<QuotaLimits> {
    const response = await api.get(API_ENDPOINTS.USAGE.QUOTAS);
    return response.data;
  }

  async getAssetLimits(): Promise<{
    can_create: boolean;
    current_count: number;
    limit: number;
    usage_percent: number;
  }> {
    const response = await api.get(API_ENDPOINTS.USAGE.LIMITS_ASSETS);
    return response.data;
  }

  async getScanLimits(): Promise<{
    can_start_scan: boolean;
    daily_usage: {
      current: number;
      limit: number;
      usage_percent: number;
      limit_reached: boolean;
    };
    monthly_usage: {
      current: number;
      limit: number;
      usage_percent: number;
      limit_reached: boolean;
    };
    concurrent_usage: {
      current: number;
      limit: number;
      usage_percent: number;
      limit_reached: boolean;
    };
  }> {
    const response = await api.get(API_ENDPOINTS.USAGE.LIMITS_SCANS);
    return response.data;
  }
}

// Export singleton instance
export const usageAPI = new UsageAPI();

// Export default
export default usageAPI;
