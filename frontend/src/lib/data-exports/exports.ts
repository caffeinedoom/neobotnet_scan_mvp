/**
 * Scalable Export System for Reconnaissance Data
 * 
 * This module provides a unified interface for exporting various types of
 * reconnaissance data in different formats. Designed to scale with future
 * reconnaissance modules (DNS, HTTP probing, etc.).
 */

import { toast } from 'sonner';

// Export format types
export enum ExportFormat {
  CSV = 'csv',
  JSON = 'json',
  TXT = 'txt'
}

// Base interface for exportable data
export interface ExportableData {
  [key: string]: string | number | boolean | null | undefined;
}

// Export configuration
export interface ExportConfig<T extends ExportableData> {
  data: T[];
  filename: string;
  format: ExportFormat;
  columns?: Array<keyof T>;
  customHeaders?: Record<keyof T, string>;
}

// Specific data type interfaces for type safety
export interface SubdomainExportData extends ExportableData {
  subdomain: string;
  domain: string;
  discovered_at: string;
  scan_job_id: string;
}

export interface ScanJobExportData extends ExportableData {
  domain: string;
  scan_type: string;
  status: string;
  created_at: string;
  result_count: number;
  completed_at?: string;
}

// Future data types for upcoming modules
export interface DNSRecordExportData extends ExportableData {
  domain: string;
  record_type: string;
  value: string;
  ttl?: number;
  discovered_at: string;
}

export interface HTTPProbeExportData extends ExportableData {
  url: string;
  status_code?: number;
  title?: string;
  server?: string;
  content_length?: number;
  response_time?: number;
  discovered_at: string;
}

/**
 * Core Export Service
 */
class ExportService {
  /**
   * Convert data to CSV format
   */
  private toCsv<T extends ExportableData>(
    data: T[],
    columns?: Array<keyof T>,
    customHeaders?: Record<keyof T, string>
  ): string {
    if (data.length === 0) return '';

    // Determine columns to export
    const exportColumns = columns || (Object.keys(data[0]) as Array<keyof T>);
    
    // Create headers
    const headers = exportColumns.map(col => 
      customHeaders?.[col] || String(col).replace(/_/g, ' ').toUpperCase()
    );
    
    // Create CSV content
    const csvLines = [
      headers.join(','),
      ...data.map(row => 
        exportColumns.map(col => {
          const value = row[col];
          // Escape CSV values
          if (typeof value === 'string' && (value.includes(',') || value.includes('"') || value.includes('\n'))) {
            return `"${value.replace(/"/g, '""')}"`;
          }
          return value ?? '';
        }).join(',')
      )
    ];
    
    return csvLines.join('\n');
  }

  /**
   * Convert data to JSON format
   */
  private toJson<T extends ExportableData>(
    data: T[],
    columns?: Array<keyof T>
  ): string {
    if (columns) {
      // Filter to only include specified columns
      const filteredData = data.map(row => {
        const filtered: Partial<T> = {};
        columns.forEach(col => {
          filtered[col] = row[col];
        });
        return filtered;
      });
      return JSON.stringify(filteredData, null, 2);
    }
    
    return JSON.stringify(data, null, 2);
  }

  /**
   * Convert data to plain text format
   */
  private toTxt<T extends ExportableData>(
    data: T[],
    columns?: Array<keyof T>
  ): string {
    if (data.length === 0) return '';

    const exportColumns = columns || (Object.keys(data[0]) as Array<keyof T>);
    
    return data.map(row => 
      exportColumns.map(col => row[col]).join('\t')
    ).join('\n');
  }

  /**
   * Download file with given content
   */
  private downloadFile(content: string, filename: string, mimeType: string): void {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    
    // Cleanup
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  /**
   * Generate filename with timestamp
   */
  private generateFilename(baseName: string, format: ExportFormat): string {
    const timestamp = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    return `${baseName}_${timestamp}.${format}`;
  }

  /**
   * Main export function
   */
  async export<T extends ExportableData>(config: ExportConfig<T>): Promise<void> {
    try {
      if (config.data.length === 0) {
        toast.error('No data to export');
        return;
      }

      let content: string;
      let mimeType: string;
      let filename: string;

      switch (config.format) {
        case ExportFormat.CSV:
          content = this.toCsv(config.data, config.columns, config.customHeaders);
          mimeType = 'text/csv;charset=utf-8;';
          filename = this.generateFilename(config.filename, ExportFormat.CSV);
          break;

        case ExportFormat.JSON:
          content = this.toJson(config.data, config.columns);
          mimeType = 'application/json;charset=utf-8;';
          filename = this.generateFilename(config.filename, ExportFormat.JSON);
          break;

        case ExportFormat.TXT:
          content = this.toTxt(config.data, config.columns);
          mimeType = 'text/plain;charset=utf-8;';
          filename = this.generateFilename(config.filename, ExportFormat.TXT);
          break;

        default:
          throw new Error(`Unsupported export format: ${config.format}`);
      }

      this.downloadFile(content, filename, mimeType);
      toast.success(`Exported ${config.data.length} records as ${config.format.toUpperCase()}`);

    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Export failed. Please try again.');
    }
  }
}

// Create singleton instance
export const exportService = new ExportService();

/**
 * Convenience functions for specific data types
 */

// Subdomain exports
export const exportSubdomains = async (
  data: SubdomainExportData[],
  format: ExportFormat = ExportFormat.CSV
) => {
  await exportService.export({
    data,
    filename: 'subdomains',
    format,
    columns: ['subdomain', 'domain', 'discovered_at', 'ip_addresses'],
    customHeaders: {
      subdomain: 'Subdomain',
      domain: 'Root Domain',
      discovered_at: 'Discovered Date',
      ip_addresses: 'IP Addresses'
    }
  });
};

// Scan job exports
export const exportScanJobs = async (
  data: ScanJobExportData[],
  format: ExportFormat = ExportFormat.CSV
) => {
  await exportService.export({
    data,
    filename: 'scan_jobs',
    format,
    columns: ['domain', 'scan_type', 'status', 'created_at', 'result_count', 'completed_at'],
    customHeaders: {
      domain: 'Domain',
      scan_type: 'Scan Type',
      status: 'Status',
      created_at: 'Started',
      result_count: 'Results',
      completed_at: 'Completed'
    }
  });
};

// Future export functions for upcoming modules
export const exportDNSRecords = async (
  data: DNSRecordExportData[],
  format: ExportFormat = ExportFormat.CSV
) => {
  await exportService.export({
    data,
    filename: 'dns_records',
    format,
    columns: ['domain', 'record_type', 'value', 'ttl', 'discovered_at'],
    customHeaders: {
      domain: 'Domain',
      record_type: 'Record Type',
      value: 'Value',
      ttl: 'TTL',
      discovered_at: 'Discovered Date'
    }
  });
};

export const exportHTTPProbes = async (
  data: HTTPProbeExportData[],
  format: ExportFormat = ExportFormat.CSV
) => {
  await exportService.export({
    data,
    filename: 'http_probes',
    format,
    columns: ['url', 'status_code', 'title', 'server', 'content_length', 'response_time', 'discovered_at'],
    customHeaders: {
      url: 'URL',
      status_code: 'Status Code',
      title: 'Page Title',
      server: 'Server',
      content_length: 'Content Length',
      response_time: 'Response Time (ms)',
      discovered_at: 'Discovered Date'
    }
  });
};
