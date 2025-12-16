/**
 * Centralized API Client for NeoBot-Net LEAN
 * 
 * This client automatically includes the Supabase JWT token
 * in all API requests for authentication.
 * 
 * Usage:
 *   import { apiClient } from '@/lib/api/client';
 *   const data = await apiClient.get('/api/v1/programs');
 */
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { supabase } from '@/lib/supabase';
import { API_BASE_URL } from './config';

// Create axios instance with base configuration
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: 30000, // 30 second timeout
  });

  // Request interceptor to add authentication token
  client.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
      try {
        // Get current session from Supabase
        const { data: { session }, error } = await supabase.auth.getSession();
        
        if (error) {
          console.warn('Failed to get Supabase session:', error.message);
        }
        
        if (session?.access_token) {
          // Add Bearer token to Authorization header
          config.headers.Authorization = `Bearer ${session.access_token}`;
        } else {
          console.warn('No active session - request may fail with 401');
        }
      } catch (err) {
        console.error('Error in auth interceptor:', err);
      }
      
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor to handle errors
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const status = error.response?.status;
      
      if (status === 401) {
        console.warn('401 Unauthorized - Session may have expired');
        
        // Try to refresh the session
        try {
          const { data: { session }, error: refreshError } = await supabase.auth.refreshSession();
          
          if (refreshError || !session) {
            console.warn('Failed to refresh session - user may need to re-authenticate');
            // DON'T automatically redirect - let the AuthContext handle this
            // The redirect was causing logout loops when API calls happened before session was ready
          } else {
            // Retry the original request with new token
            const originalRequest = error.config;
            if (originalRequest) {
              originalRequest.headers.Authorization = `Bearer ${session.access_token}`;
              return client(originalRequest);
            }
          }
        } catch (refreshErr) {
          console.error('Session refresh failed:', refreshErr);
        }
      }
      
      if (status === 403) {
        console.error('403 Forbidden - Access denied');
      }
      
      if (status === 500) {
        console.error('500 Internal Server Error:', error.response?.data);
      }
      
      return Promise.reject(error);
    }
  );

  return client;
};

// Export singleton instance
export const apiClient = createApiClient();

// Export convenience methods
export const api = {
  get: <T = unknown>(url: string, config?: object) => 
    apiClient.get<T>(url, config).then(res => res.data),
  
  post: <T = unknown>(url: string, data?: object, config?: object) => 
    apiClient.post<T>(url, data, config).then(res => res.data),
  
  put: <T = unknown>(url: string, data?: object, config?: object) => 
    apiClient.put<T>(url, data, config).then(res => res.data),
  
  patch: <T = unknown>(url: string, data?: object, config?: object) => 
    apiClient.patch<T>(url, data, config).then(res => res.data),
  
  delete: <T = unknown>(url: string, config?: object) => 
    apiClient.delete<T>(url, config).then(res => res.data),
};

export default apiClient;

