import axios, { AxiosResponse } from 'axios';
import { UserRegister, UserLogin, LoginResponse, RegisterResponse, UserResponse } from '@/types/auth';
import { SubdomainScanRequest, ScanResponse, ScanJob, ScanJobWithResults, ScanProgress, EnhancedSubdomain } from '@/types/recon';
import { API_BASE_URL } from '@/lib/api/config';

// Use centralized API configuration

// Create axios instance
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

// Auth API functions
export const authAPI = {
  // Register new user
  register: async (userData: UserRegister): Promise<RegisterResponse> => {
    const response: AxiosResponse<RegisterResponse> = await api.post('/auth/register', userData);
    return response.data;
  },

  // Login user - now returns success message, token is set as httpOnly cookie
  login: async (credentials: UserLogin): Promise<LoginResponse> => {
    const response: AxiosResponse<LoginResponse> = await api.post('/auth/login', credentials);
    return response.data;
  },

  // Get current user profile
  me: async (): Promise<UserResponse> => {
    const response: AxiosResponse<UserResponse> = await api.get('/auth/me');
    return response.data;
  },

  // Logout user
  logout: async (): Promise<{ message: string }> => {
    const response: AxiosResponse<{ message: string }> = await api.post('/auth/logout');
    return response.data;
  },

  // Health check
  health: async (): Promise<{ status: string; service: string; message: string }> => {
    const response = await api.get('/auth/health');
    return response.data;
  },
};

// Reconnaissance API functions
export const reconAPI = {
  // Start subdomain scan with multi-module support
  startSubdomainScan: async (request: SubdomainScanRequest): Promise<ScanResponse> => {
    const response: AxiosResponse<ScanResponse> = await api.post('/recon/subdomain/scan', request);
    return response.data;
  },

  // Get scan job status and results
  getScanJob: async (jobId: string): Promise<ScanJobWithResults> => {
    const response: AxiosResponse<ScanJobWithResults> = await api.get(`/recon/jobs/${jobId}`);
    return response.data;
  },

  // Get real-time scan progress with detailed metrics
  getScanProgress: async (jobId: string): Promise<ScanProgress> => {
    const response: AxiosResponse<ScanProgress> = await api.get(`/recon/jobs/${jobId}/progress`);
    return response.data;
  },

  // Get detailed error information for a scan job
  getScanErrors: async (jobId: string): Promise<Record<string, unknown>> => {
    const response: AxiosResponse<Record<string, unknown>> = await api.get(`/recon/jobs/${jobId}/errors`);
    return response.data;
  },

  // Get real-time streaming progress data for live monitoring
  streamScanProgress: async (jobId: string): Promise<Record<string, unknown>> => {
    const response: AxiosResponse<Record<string, unknown>> = await api.get(`/recon/jobs/${jobId}/stream`);
    return response.data;
  },

  // Get enhanced subdomains with full metadata (new endpoint to be created)
  getEnhancedSubdomains: async (jobId: string): Promise<EnhancedSubdomain[]> => {
    try {
      const response: AxiosResponse<EnhancedSubdomain[]> = await api.get(`/recon/jobs/${jobId}/subdomains`);
      return response.data;
          } catch {
        // Fallback to basic scan job data if enhanced endpoint doesn't exist yet
        console.warn('Enhanced subdomains endpoint not available, falling back to basic data');
        const scanJob = await reconAPI.getScanJob(jobId);
      
      // Convert basic subdomains to enhanced format
      if (Array.isArray(scanJob.subdomains) && typeof scanJob.subdomains[0] === 'string') {
        return (scanJob.subdomains as string[]).map((subdomain, index) => ({
          id: `${jobId}-${index}`,
          subdomain,
          scan_job_id: jobId,
          source_module: 'subfinder', // Default assumption
          discovered_at: scanJob.created_at,
        })) as EnhancedSubdomain[];
      }
      
      return scanJob.subdomains as EnhancedSubdomain[];
    }
  },

  // List user's scan jobs
  listScanJobs: async (limit: number = 10): Promise<ScanJob[]> => {
    const response: AxiosResponse<ScanJob[]> = await api.get(`/recon/jobs?limit=${limit}`);
    return response.data;
  },

  // Health check for recon service
  health: async (): Promise<{ status: string; service: string; message: string }> => {
    const response = await api.get('/recon/health');
    return response.data;
  },
};

// Main API health check
export const healthCheck = async (): Promise<{ status: string; service: string; environment: string; debug: boolean }> => {
  const response = await axios.get(`${API_BASE_URL}/health`);
  return response.data;
};

export default api; 