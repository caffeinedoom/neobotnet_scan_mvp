'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Search, Server, Copy, Calendar, ArrowLeft, Download, FileText, ChevronLeft, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';
import { assetAPI } from '@/lib/api/assets';

// ================================================================
// Types and Interfaces - GROUPED VERSION
// ================================================================

interface DNSRecordDetail {
  id: string;
  record_value: string;
  ttl: number | null;
  priority: number | null;
  resolved_at: string;
  cloud_provider: string | null;
}

interface DNSRecordsByType {
  A?: DNSRecordDetail[];
  AAAA?: DNSRecordDetail[];
  CNAME?: DNSRecordDetail[];
  MX?: DNSRecordDetail[];
  TXT?: DNSRecordDetail[];
}

interface GroupedDNSRecord {
  subdomain: string;
  parent_domain: string;
  asset_name: string;
  asset_id: string;
  total_records: number;
  last_resolved: string;
  records_by_type: DNSRecordsByType;
}

interface PaginatedGroupedDNSResponse {
  grouped_records: GroupedDNSRecord[];
  pagination: {
    total: number; // Total unique subdomains
    page: number;
    per_page: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
  filters: {
    asset_id: string | null;
    parent_domain: string | null;
    record_type: string | null;
    search: string | null;
  };
  stats: {
    total_subdomains: number;
    total_dns_records: number;
    total_assets: number;
    record_type_breakdown: Record<string, number>;
  };
}

interface Asset {
  id: string;
  name: string;
  description?: string;
}

// ================================================================
// Helper Components
// ================================================================

interface RecordTypeSectionProps {
  type: 'A' | 'AAAA' | 'CNAME' | 'MX' | 'TXT';
  records: DNSRecordDetail[];
  color: string;
}

function RecordTypeSection({ type, records, color }: RecordTypeSectionProps) {
  const [expanded, setExpanded] = useState(records.length <= 3);
  const COLLAPSE_THRESHOLD = 3;
  
  if (records.length === 0) return null;
  
  const displayedRecords = expanded ? records : records.slice(0, COLLAPSE_THRESHOLD);
  const hasMore = records.length > COLLAPSE_THRESHOLD;
  
  // Format record value based on type
  const formatRecordValue = (record: DNSRecordDetail) => {
    const { record_value, ttl, priority } = record;
    
    switch (type) {
      case 'A':
      case 'AAAA':
        return `→ ${record_value}${ttl ? ` (TTL: ${ttl}s)` : ''}`;
      case 'CNAME':
        return `→ ${record_value}`;
      case 'MX':
        return `→ ${record_value}${priority ? ` (Priority: ${priority})` : ''}`;
      case 'TXT':
        return record_value.length > 100 
          ? `"${record_value.substring(0, 100)}..."`
          : `"${record_value}"`;
      default:
        return record_value;
    }
  };
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className={`text-sm font-semibold ${color}`}>
          {type} Records ({records.length})
        </h4>
        {hasMore && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            className="h-6 px-2 text-xs"
          >
            {expanded ? (
              <>
                <ChevronUp className="h-3 w-3 mr-1" />
                Show less
              </>
            ) : (
              <>
                <ChevronDown className="h-3 w-3 mr-1" />
                Show {records.length - COLLAPSE_THRESHOLD} more
              </>
            )}
          </Button>
        )}
      </div>
      <div className="space-y-1 pl-2">
        {displayedRecords.map((record, idx) => (
          <div key={record.id || idx} className="text-sm text-muted-foreground font-mono">
            {formatRecordValue(record)}
          </div>
        ))}
      </div>
    </div>
  );
}

// ================================================================
// Loading Component
// ================================================================

function DNSLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  );
}

// ================================================================
// Main Component
// ================================================================

function DNSPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // URL-driven state (single source of truth)
  const page = parseInt(searchParams.get('page') || '1', 10);
  const perPage = parseInt(searchParams.get('per_page') || '50', 10);
  const assetIdParam = searchParams.get('asset_id');
  const parentDomainParam = searchParams.get('parent_domain');
  const recordTypeParam = searchParams.get('record_type');
  const searchQuery = searchParams.get('search') || '';

  // Component state
  const [dnsData, setDnsData] = useState<PaginatedGroupedDNSResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filter options state
  const [availableAssets, setAvailableAssets] = useState<Asset[]>([]);
  const [availableDomains, setAvailableDomains] = useState<string[]>([]);
  
  // Search input state (for controlled input)
  const [searchInput, setSearchInput] = useState(searchQuery);
  const [searchDebounceTimeout, setSearchDebounceTimeout] = useState<NodeJS.Timeout | null>(null);

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !authLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, authLoading, router]);

  // Fetch filter options
  useEffect(() => {
    const fetchFilterOptions = async () => {
      if (!isAuthenticated) return;
      
      try {
        const assets = await assetAPI.getAssets();
        setAvailableAssets(assets);
      } catch (err) {
        console.error('Failed to fetch filter options:', err);
      }
    };

    if (isAuthenticated) {
      fetchFilterOptions();
    }
  }, [isAuthenticated]);

  // Fetch grouped DNS records
  const fetchDNSRecords = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      setIsLoading(true);
      setError(null);

      // Build query params with grouped=true
      const params = new URLSearchParams();
      params.append('page', page.toString());
      params.append('per_page', perPage.toString());
      params.append('grouped', 'true'); // NEW: Enable grouped view
      
      if (assetIdParam) params.append('asset_id', assetIdParam);
      if (parentDomainParam) params.append('parent_domain', parentDomainParam);
      if (recordTypeParam) params.append('record_type', recordTypeParam);
      if (searchQuery) params.append('search', searchQuery);

      // Use centralized API client with JWT authentication
      const { apiClient } = await import('@/lib/api/client');
      const response = await apiClient.get<PaginatedGroupedDNSResponse>(
        `/api/v1/assets/dns-records/paginated?${params}`
      );

      const data = response.data;
      setDnsData(data);

      // Extract unique parent domains for filter dropdown
      if (data.grouped_records.length > 0) {
        const domains = Array.from(new Set(data.grouped_records.map(r => r.parent_domain))).sort();
        setAvailableDomains(domains);
      }

    } catch (err) {
      console.error('Error fetching DNS records:', err);
      setError(err instanceof Error ? err.message : 'Failed to load DNS records');
      toast.error('Failed to load DNS records');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, page, perPage, assetIdParam, parentDomainParam, recordTypeParam, searchQuery]);

  // Fetch DNS records when params change
  useEffect(() => {
    if (isAuthenticated) {
      fetchDNSRecords();
    }
  }, [isAuthenticated, fetchDNSRecords]);

  // Update URL with new params
  const updateURL = (updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === '') {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });

    router.push(`/dns?${params.toString()}`);
  };

  // Filter handlers
  const handleAssetFilter = (value: string) => {
    updateURL({ asset_id: value === 'all' ? null : value, page: '1' });
  };

  const handleDomainFilter = (value: string) => {
    updateURL({ parent_domain: value === 'all' ? null : value, page: '1' });
  };

  const handleRecordTypeFilter = (value: string) => {
    updateURL({ record_type: value === 'all' ? null : value, page: '1' });
  };

  const handlePerPageChange = (value: string) => {
    updateURL({ per_page: value, page: '1' });
  };

  const handleSearchChange = (value: string) => {
    setSearchInput(value);
    
    if (searchDebounceTimeout) {
      clearTimeout(searchDebounceTimeout);
    }
    
    const timeout = setTimeout(() => {
      updateURL({ search: value || null, page: '1' });
    }, 300);
    
    setSearchDebounceTimeout(timeout);
  };

  const handlePageChange = (newPage: number) => {
    updateURL({ page: newPage.toString() });
  };

  // Copy handlers
  const copySubdomainDNS = (record: GroupedDNSRecord) => {
    const lines: string[] = [`${record.subdomain}:`];
    
    Object.entries(record.records_by_type).forEach(([type, records]) => {
      if (records && records.length > 0) {
        lines.push(`  ${type}:`);
        records.forEach((r: DNSRecordDetail) => {
          lines.push(`    ${r.record_value}${r.ttl ? ` (TTL: ${r.ttl}s)` : ''}`);
        });
      }
    });
    
    navigator.clipboard.writeText(lines.join('\n'));
    toast.success(`DNS configuration for ${record.subdomain} copied`);
  };

  const copyAllVisible = () => {
    if (!dnsData || dnsData.grouped_records.length === 0) {
      toast.error('No DNS records to copy');
      return;
    }

    const text = dnsData.grouped_records.map(record => {
      const lines: string[] = [`${record.subdomain}:`];
      Object.entries(record.records_by_type).forEach(([type, records]) => {
        if (records && records.length > 0) {
          records.forEach((r: DNSRecordDetail) => lines.push(`  ${type}: ${r.record_value}`));
        }
      });
      return lines.join('\n');
    }).join('\n\n');
    
    navigator.clipboard.writeText(text);
    toast.success(`Copied ${dnsData.grouped_records.length} subdomains`);
  };

  // Export handlers
  const exportAsCSV = () => {
    if (!dnsData || dnsData.grouped_records.length === 0) {
      toast.error('No DNS records to export');
      return;
    }

    const headers = ['Subdomain', 'Record Type', 'Value', 'TTL', 'Priority', 'Parent Domain', 'Asset', 'Resolved At'];
    const rows: string[][] = [];
    
    dnsData.grouped_records.forEach(subdomain => {
      Object.entries(subdomain.records_by_type).forEach(([type, records]) => {
        if (records) {
          records.forEach((record: DNSRecordDetail) => {
            rows.push([
              subdomain.subdomain,
              type,
              record.record_value,
              record.ttl?.toString() || '',
              record.priority?.toString() || '',
              subdomain.parent_domain,
              subdomain.asset_name,
              new Date(record.resolved_at).toLocaleString()
            ]);
          });
        }
      });
    });

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `dns-records-grouped-page-${page}.csv`;
    link.click();
    URL.revokeObjectURL(url);

    toast.success('DNS records exported to CSV');
  };

  const exportAsJSON = () => {
    if (!dnsData || dnsData.grouped_records.length === 0) {
      toast.error('No DNS records to export');
      return;
    }

    const jsonContent = JSON.stringify(dnsData.grouped_records, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `dns-records-grouped-page-${page}.json`;
    link.click();
    URL.revokeObjectURL(url);

    toast.success('DNS records exported to JSON');
  };

  // Helper: Get badge color for record type
  const getRecordTypeBadgeColor = (recordType: string) => {
    const colors: Record<string, string> = {
      'A': 'text-blue-700 dark:text-blue-400',
      'AAAA': 'text-purple-700 dark:text-purple-400',
      'CNAME': 'text-green-700 dark:text-green-400',
      'MX': 'text-orange-700 dark:text-orange-400',
      'TXT': 'text-pink-700 dark:text-pink-400',
    };
    return colors[recordType] || 'text-gray-700 dark:text-gray-400';
  };

  // Get current asset name (if filtered)
  const currentAssetName = assetIdParam 
    ? availableAssets.find(a => a.id === assetIdParam)?.name 
    : null;

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-6">
        {/* Header Section */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center space-x-3">
              {assetIdParam && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push('/recon')}
                  className="mr-2"
                >
                  <ArrowLeft className="h-4 w-4 mr-1" />
                  Back
                </Button>
              )}
              <div className="flex items-center space-x-2">
                <Server className="h-6 w-6 text-primary" />
                <h1 className="text-3xl font-bold tracking-tight">
                  DNS Records
                  {dnsData && (
                    <span className="text-muted-foreground ml-2 text-2xl">
                      {dnsData.stats.total_subdomains.toLocaleString()}
                    </span>
                  )}
                </h1>
              </div>
            </div>
            
            {currentAssetName && (
              <p className="text-muted-foreground mt-2">
                DNS records for {currentAssetName}
              </p>
            )}
            {dnsData && dnsData.stats.total_dns_records > 0 && (
              <p className="text-sm text-muted-foreground">
                {dnsData.stats.total_dns_records.toLocaleString()} total DNS records across all subdomains
              </p>
            )}
          </div>
        </div>

        {/* Filters Card */}
        <Card>
          <CardHeader>
            <CardTitle>Filters & Search</CardTitle>
            <CardDescription>
              Filter DNS records by asset, domain, type, or search by subdomain name
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              {/* Search Input */}
              <div className="lg:col-span-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search subdomains..."
                    value={searchInput}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>

              {/* Asset Filter */}
              <div>
                <Select
                  value={assetIdParam || 'all'}
                  onValueChange={handleAssetFilter}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All Assets" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Assets</SelectItem>
                    {availableAssets.map((asset) => (
                      <SelectItem key={asset.id} value={asset.id}>
                        {asset.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Parent Domain Filter */}
              <div>
                <Select
                  value={parentDomainParam || 'all'}
                  onValueChange={handleDomainFilter}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All Domains" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Domains</SelectItem>
                    {availableDomains.map((domain) => (
                      <SelectItem key={domain} value={domain}>
                        {domain}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Record Type Filter */}
              <div>
                <Select
                  value={recordTypeParam || 'all'}
                  onValueChange={handleRecordTypeFilter}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All Types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="A">A</SelectItem>
                    <SelectItem value="AAAA">AAAA</SelectItem>
                    <SelectItem value="CNAME">CNAME</SelectItem>
                    <SelectItem value="MX">MX</SelectItem>
                    <SelectItem value="TXT">TXT</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-2 mt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={copyAllVisible}
                disabled={!dnsData || dnsData.grouped_records.length === 0}
              >
                <Copy className="h-4 w-4 mr-2" />
                Copy All ({dnsData?.grouped_records.length || 0})
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={exportAsCSV}
                disabled={!dnsData || dnsData.grouped_records.length === 0}
              >
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={exportAsJSON}
                disabled={!dnsData || dnsData.grouped_records.length === 0}
              >
                <FileText className="h-4 w-4 mr-2" />
                Export JSON
              </Button>
              
              {/* Per Page Selector */}
              <div className="ml-auto flex items-center space-x-2">
                <span className="text-sm text-muted-foreground">Per page:</span>
                <Select
                  value={perPage.toString()}
                  onValueChange={handlePerPageChange}
                >
                  <SelectTrigger className="w-[100px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="25">25</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                    <SelectItem value="100">100</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results Card */}
        <Card>
          <CardHeader>
            <CardTitle>DNS Records by Subdomain</CardTitle>
            <CardDescription>
              {dnsData && `Showing ${dnsData.grouped_records.length} of ${dnsData.pagination.total.toLocaleString()} subdomains`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Loading State */}
            {isLoading && (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            )}

            {/* Error State */}
            {error && !isLoading && (
              <div className="text-center py-12">
                <p className="text-red-500">{error}</p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={fetchDNSRecords}
                >
                  Retry
                </Button>
              </div>
            )}

            {/* Empty State */}
            {!isLoading && !error && dnsData && dnsData.grouped_records.length === 0 && (
              <div className="text-center py-12">
                <Server className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
                <h3 className="mt-4 text-lg font-semibold">No DNS records found</h3>
                <p className="text-muted-foreground mt-2">
                  {searchQuery || assetIdParam || parentDomainParam || recordTypeParam
                    ? 'Try adjusting your filters or search query'
                    : 'Run a scan to discover DNS records'}
                </p>
              </div>
            )}

            {/* Grouped DNS Records List */}
            {!isLoading && !error && dnsData && dnsData.grouped_records.length > 0 && (
              <div className="space-y-4">
                {dnsData.grouped_records.map((record) => (
                  <Card key={record.subdomain} className="hover:border-primary/50 transition-colors">
                    <CardContent className="pt-6">
                      {/* Header Row */}
                      <div className="flex items-start justify-between gap-2 mb-4 pb-4 border-b">
                        <div className="flex-1 space-y-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <code className="text-base font-mono font-semibold bg-muted px-2 py-1 rounded">
                              {record.subdomain}
                            </code>
                            <Badge variant="outline" className="text-xs">
                              {record.parent_domain}
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                              {record.asset_name}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-muted-foreground">
                            <span>{record.total_records} DNS records</span>
                            <span>•</span>
                            <div className="flex items-center">
                              <Calendar className="h-3 w-3 mr-1" />
                              Last resolved {formatDistanceToNow(new Date(record.last_resolved), { addSuffix: true })}
                            </div>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => copySubdomainDNS(record)}
                          title="Copy all DNS records for this subdomain"
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>

                      {/* DNS Records by Type */}
                      <div className="space-y-4">
                        {record.records_by_type.A && record.records_by_type.A.length > 0 && (
                          <RecordTypeSection 
                            type="A" 
                            records={record.records_by_type.A}
                            color={getRecordTypeBadgeColor('A')}
                          />
                        )}
                        {record.records_by_type.AAAA && record.records_by_type.AAAA.length > 0 && (
                          <RecordTypeSection 
                            type="AAAA" 
                            records={record.records_by_type.AAAA}
                            color={getRecordTypeBadgeColor('AAAA')}
                          />
                        )}
                        {record.records_by_type.CNAME && record.records_by_type.CNAME.length > 0 && (
                          <RecordTypeSection 
                            type="CNAME" 
                            records={record.records_by_type.CNAME}
                            color={getRecordTypeBadgeColor('CNAME')}
                          />
                        )}
                        {record.records_by_type.MX && record.records_by_type.MX.length > 0 && (
                          <RecordTypeSection 
                            type="MX" 
                            records={record.records_by_type.MX}
                            color={getRecordTypeBadgeColor('MX')}
                          />
                        )}
                        {record.records_by_type.TXT && record.records_by_type.TXT.length > 0 && (
                          <RecordTypeSection 
                            type="TXT" 
                            records={record.records_by_type.TXT}
                            color={getRecordTypeBadgeColor('TXT')}
                          />
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Pagination Controls */}
            {!isLoading && !error && dnsData && dnsData.pagination.total_pages > 1 && (
              <div className="flex items-center justify-between mt-6 pt-6 border-t">
                <div className="text-sm text-muted-foreground">
                  Page {dnsData.pagination.page} of {dnsData.pagination.total_pages}
                </div>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(page - 1)}
                    disabled={!dnsData.pagination.has_prev}
                  >
                    <ChevronLeft className="h-4 w-4 mr-1" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(page + 1)}
                    disabled={!dnsData.pagination.has_next}
                  >
                    Next
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ================================================================
// Export with Suspense Boundary
// ================================================================

export default function DNSPage() {
  return (
    <Suspense fallback={<DNSLoading />}>
      <DNSPageContent />
    </Suspense>
  );
}
