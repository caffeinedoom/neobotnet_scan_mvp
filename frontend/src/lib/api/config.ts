// API Configuration - Dynamic backend URL detection
function getBackendURL(): string {
  // If we have explicit environment variables, use them
  if (process.env.NEXT_PUBLIC_LINODE_ENVIRONMENT) {
    return process.env.NEXT_PUBLIC_LINODE_ENVIRONMENT;
  }
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // For client-side, detect backend URL based on current host
  if (typeof window !== 'undefined') {
    const currentHost = window.location.hostname;
    
    // If accessing via IP address, use the same IP for backend
    if (currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
      return `http://${currentHost}:8000`;
    }
  }
  
  // Default fallback
  return 'http://localhost:8000';
}

export const API_BASE_URL = getBackendURL();
export const API_VERSION = 'v1';

// API Endpoints
export const API_ENDPOINTS = {
  // Authentication
  AUTH: {
    LOGIN: '/api/v1/auth/login',
    REGISTER: '/api/v1/auth/register',
    REFRESH: '/api/v1/auth/refresh',
    LOGOUT: '/api/v1/auth/logout',
    PROFILE: '/api/v1/auth/profile',
  },
  
  // Assets
  ASSETS: {
    LIST: '/api/v1/assets/',
    CREATE: '/api/v1/assets/',
    GET: (id: string) => `/api/v1/assets/${id}`,
    UPDATE: (id: string) => `/api/v1/assets/${id}`,
    DELETE: (id: string) => `/api/v1/assets/${id}`,
    SCAN: (id: string) => `/api/v1/assets/${id}/scan`,
    ANALYTICS: (id: string) => `/api/v1/assets/${id}/analytics`,
    DOMAINS: (id: string) => `/api/v1/assets/${id}/domains`,
    SUMMARY: '/api/v1/assets/summary',
    BULK: '/api/v1/assets/bulk',
  },
  
  // Apex Domains
  DOMAINS: {
    CREATE: (assetId: string) => `/api/v1/assets/${assetId}/domains`,
    GET: (assetId: string, domainId: string) => `/api/v1/assets/${assetId}/domains/${domainId}`,
    UPDATE: (assetId: string, domainId: string) => `/api/v1/assets/${assetId}/domains/${domainId}`,
    DELETE: (assetId: string, domainId: string) => `/api/v1/assets/${assetId}/domains/${domainId}`,
  },
  
  // Usage & Quotas
  USAGE: {
    OVERVIEW: '/api/v1/usage/overview',
    QUOTAS: '/api/v1/usage/quotas',
    LIMITS_ASSETS: '/api/v1/usage/limits/assets',
    LIMITS_SCANS: '/api/v1/usage/limits/scans',
    DASHBOARD_STATS: '/api/v1/usage/dashboard-stats',
    RECON_DATA: '/api/v1/usage/recon-data', // Unified reconnaissance data service
  },
  
  // Reconnaissance
  RECON: {
    SCAN_JOBS: '/api/v1/recon/scan-jobs',
    SUBDOMAINS: '/api/v1/recon/subdomains',
    START_SCAN: '/api/v1/recon/subdomain-scan',
  },
  
  // DNS Records
  DNS: {
    RECORDS_BY_ASSET: (assetId: string) => `/api/v1/assets/${assetId}/dns-records`,
    RECORD_BY_ID: (recordId: string) => `/api/v1/dns-records/${recordId}`,
  },
} as const;

// Request timeout (in milliseconds)
export const REQUEST_TIMEOUT = 30000;

// Default headers
export const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
} as const;
