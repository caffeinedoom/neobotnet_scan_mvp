// API Configuration - Dynamic backend URL detection
function getBackendURL(): string {
  // Priority 1: Explicit API URL from environment
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // Priority 2: Legacy Linode environment variable
  if (process.env.NEXT_PUBLIC_LINODE_ENVIRONMENT) {
    return process.env.NEXT_PUBLIC_LINODE_ENVIRONMENT;
  }
  
  // Priority 3: For local development
  if (typeof window !== 'undefined') {
    const currentHost = window.location.hostname;
    
    // Local development - use localhost backend
    if (currentHost === 'localhost' || currentHost === '127.0.0.1') {
      return 'http://localhost:8000';
    }
    
    // IP-based access (e.g., Linode direct)
    const ipPattern = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;
    if (ipPattern.test(currentHost)) {
      return `http://${currentHost}:8000`;
    }
    
    // IMPORTANT: For Vercel/production deployments, API_URL MUST be set
    // If we reach here in production without NEXT_PUBLIC_API_URL, 
    // log a warning and return empty to avoid wrong host requests
    console.warn(
      '⚠️ No NEXT_PUBLIC_API_URL configured. API calls will fail in production.',
      'Please set NEXT_PUBLIC_API_URL in Vercel environment variables.'
    );
  }
  
  // Default fallback for local dev
  return 'http://localhost:8000';
}

export const API_BASE_URL = getBackendURL();

// Log API configuration for debugging
if (typeof window !== 'undefined') {
  console.log('🔧 API Configuration:', {
    API_BASE_URL,
    hasEnvVar: !!process.env.NEXT_PUBLIC_API_URL
  });
}
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
