/**
 * Export Service - Handles data exports (CSV/JSON)
 * 
 * URLs export requires PRO subscription.
 * All other exports are free.
 */

import { apiClient } from './client';
import { toast } from 'sonner';

export type ExportFormat = 'csv' | 'json';

export interface URLExportFilters {
  asset_id?: string;
  is_alive?: boolean;
  status_code?: number;
  has_params?: boolean;
}

export interface SubdomainExportFilters {
  asset_id?: string;
  parent_domain?: string;
}

export interface DNSExportFilters {
  asset_id?: string;
  record_type?: string;
  subdomain?: string;
}

export interface ProbeExportFilters {
  asset_id?: string;
  status_code?: number;
}

/**
 * Download a blob as a file
 */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Build query string from filters
 */
function buildQueryString(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.append(key, String(value));
    }
  });
  return params.toString();
}

/**
 * Export URLs (PRO ONLY)
 */
export async function exportURLs(
  format: ExportFormat,
  filters: URLExportFilters = {}
): Promise<void> {
  try {
    toast.loading('Preparing URL export...', { id: 'url-export' });
    
    const queryString = buildQueryString({ format, ...filters });
    const response = await apiClient.get<Blob>(`/exports/urls?${queryString}`, {
      responseType: 'blob',
    });
    
    const filename = `urls-export.${format}`;
    downloadBlob(response.data, filename);
    
    toast.success(`URLs exported as ${format.toUpperCase()}`, { id: 'url-export' });
  } catch (error: unknown) {
    console.error('URL export failed:', error);
    
    // Check for 403 (PRO required)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { status?: number; data?: unknown } };
      if (axiosError.response?.status === 403) {
        toast.error('URL export requires a Pro subscription', { id: 'url-export' });
        return;
      }
    }
    
    toast.error('Failed to export URLs', { id: 'url-export' });
  }
}

/**
 * Export Subdomains (FREE)
 */
export async function exportSubdomains(
  format: ExportFormat,
  filters: SubdomainExportFilters = {}
): Promise<void> {
  try {
    toast.loading('Preparing subdomain export...', { id: 'subdomain-export' });
    
    const queryString = buildQueryString({ format, ...filters });
    const response = await apiClient.get<Blob>(`/exports/subdomains?${queryString}`, {
      responseType: 'blob',
    });
    
    const filename = `subdomains-export.${format}`;
    downloadBlob(response.data, filename);
    
    toast.success(`Subdomains exported as ${format.toUpperCase()}`, { id: 'subdomain-export' });
  } catch (error) {
    console.error('Subdomain export failed:', error);
    toast.error('Failed to export subdomains', { id: 'subdomain-export' });
  }
}

/**
 * Export DNS Records (FREE)
 */
export async function exportDNSRecords(
  format: ExportFormat,
  filters: DNSExportFilters = {}
): Promise<void> {
  try {
    toast.loading('Preparing DNS export...', { id: 'dns-export' });
    
    const queryString = buildQueryString({ format, ...filters });
    const response = await apiClient.get<Blob>(`/exports/dns?${queryString}`, {
      responseType: 'blob',
    });
    
    const filename = `dns-records-export.${format}`;
    downloadBlob(response.data, filename);
    
    toast.success(`DNS records exported as ${format.toUpperCase()}`, { id: 'dns-export' });
  } catch (error) {
    console.error('DNS export failed:', error);
    toast.error('Failed to export DNS records', { id: 'dns-export' });
  }
}

/**
 * Export HTTP Probes (FREE)
 */
export async function exportHTTPProbes(
  format: ExportFormat,
  filters: ProbeExportFilters = {}
): Promise<void> {
  try {
    toast.loading('Preparing HTTP probes export...', { id: 'probe-export' });
    
    const queryString = buildQueryString({ format, ...filters });
    const response = await apiClient.get<Blob>(`/exports/probes?${queryString}`, {
      responseType: 'blob',
    });
    
    const filename = `http-probes-export.${format}`;
    downloadBlob(response.data, filename);
    
    toast.success(`HTTP probes exported as ${format.toUpperCase()}`, { id: 'probe-export' });
  } catch (error) {
    console.error('HTTP probes export failed:', error);
    toast.error('Failed to export HTTP probes', { id: 'probe-export' });
  }
}
