'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Search, Globe, Copy, Calendar, ArrowLeft, Download, FileText, ChevronLeft, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { exportSubdomains } from '@/lib/api/exports';
// DNS data hooks commented out - not needed for clean subdomain display
// import { useDNSData, useAssetIdsFromSubdomains } from '@/lib/hooks/useDNSData';

// ================================================================
// NEW: Pagination Types & Interfaces
// ================================================================

interface PaginationInfo {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

interface SubdomainFilters {
  asset_id?: string;
  parent_domain?: string;
  search?: string;
}

interface SubdomainWithAssetInfo {
  id: string;
  subdomain: string;
  discovered_at: string;
  parent_domain: string;
  scan_job_id: string;
  asset_id: string;
  asset_name: string;
  scan_job_domain: string;
  scan_job_type: string;
  scan_job_status: string;
  scan_job_created_at: string;
}

interface PaginatedSubdomainResponse {
  subdomains: SubdomainWithAssetInfo[];
  pagination: PaginationInfo;
  filters: SubdomainFilters;
  stats: Record<string, unknown>;
}

// ================================================================
// NEW: Efficient Pagination API Call
// ================================================================

async function fetchPaginatedSubdomains(params: {
  page?: number;
  per_page?: number;
  asset_id?: string;
  parent_domain?: string;
  search?: string;
}): Promise<PaginatedSubdomainResponse> {
  const searchParams = new URLSearchParams();
  
  if (params.page) searchParams.append('page', params.page.toString());
  if (params.per_page) searchParams.append('per_page', params.per_page.toString());
  if (params.asset_id) searchParams.append('asset_id', params.asset_id);
  if (params.parent_domain) searchParams.append('parent_domain', params.parent_domain);
  if (params.search) searchParams.append('search', params.search);

  // Use centralized API client with JWT authentication
  try {
    const { apiClient } = await import('@/lib/api/client');
    
    const response = await apiClient.get<PaginatedSubdomainResponse>(
      `/api/v1/assets/subdomains/paginated?${searchParams}`
    );

    return response.data;
  } catch (error) {
    // Log the actual error for debugging
    console.error('Paginated subdomains API error:', error);
    
    // Re-throw to let the caller handle it properly
    // This ensures users see the actual error instead of silently falling back
    throw error;
  }
}

// Component that uses searchParams - needs to be wrapped in Suspense
function SubdomainsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();
  
  // ================================================================
  // NEW: URL-Driven State Management (Single Source of Truth)
  // ================================================================
  
  // All state derived from URL - no useState for filters/pagination
  const currentPage = parseInt(searchParams.get('page') || '1');
  const perPage = parseInt(searchParams.get('per_page') || '50');
  const searchTerm = searchParams.get('search') || '';
  const selectedDomain = searchParams.get('parent_domain') || 'all';
  const selectedAsset = searchParams.get('asset') || 'all';

  // Only loading state and data need useState
  const [subdomainData, setSubdomainData] = useState<PaginatedSubdomainResponse | null>(null);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Available filter options (populated from data)
  const [availableDomains, setAvailableDomains] = useState<string[]>([]);
  const [availableAssets, setAvailableAssets] = useState<{id: string, name: string}[]>([]);

  // ================================================================
  // DNS Data Integration - DISABLED FOR CLEAN UI
  // ================================================================
  
  // Note: DNS data integration commented out for cleaner subdomain display
  // Can be re-enabled in the future if needed
  
  // Extract unique asset IDs from loaded subdomains
  // const assetIds = useAssetIdsFromSubdomains(subdomainData?.subdomains || []);
  
  // Fetch DNS data for all assets on the current page
  // const { 
  //   dnsData, 
  //   loading: dnsLoading, 
  //   error: dnsError, 
  //   refetch: retryDNS 
  // } = useDNSData(assetIds);

  // ================================================================
  // NEW: URL Update Helper (Seamless Navigation)
  // ================================================================

  const updateURL = useCallback((updates: Record<string, string | number | null>) => {
    const newParams = new URLSearchParams(searchParams.toString());
    
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === '' || value === 'all') {
        newParams.delete(key);
      } else {
        newParams.set(key, value.toString());
      }
    });

    // Use replace for seamless navigation (no browser history clutter)
    router.replace(`/subdomains?${newParams.toString()}`, { scroll: false });
  }, [router, searchParams]);

  // ================================================================
  // NEW: Debounced Search Implementation  
  // ================================================================

  const [debouncedSearch, setDebouncedSearch] = useState(searchTerm);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
    }, 300); // 300ms debounce

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // ================================================================
  // NEW: Efficient Data Loading (Fixed - Comprehensive Filter Scope)
  // ================================================================

  const loadSubdomains = useCallback(async () => {
    if (!isAuthenticated) return;
    
    try {
      setIsLoadingData(true);
      setError(null);
      
      const response = await fetchPaginatedSubdomains({
        page: currentPage,
        per_page: perPage,
        asset_id: selectedAsset !== 'all' ? selectedAsset : undefined,
        parent_domain: selectedDomain !== 'all' ? selectedDomain : undefined,
        search: debouncedSearch || undefined,
      });
      
      setSubdomainData(response);
      
      // Note: Filter options now loaded separately for comprehensive scope
      // No longer building from page-scoped data
      
    } catch (err) {
      console.error('Failed to load subdomains:', err);
      setError('Failed to load subdomains. Please try again.');
      toast.error('Failed to load subdomains');
    } finally {
      setIsLoadingData(false);
    }
  }, [isAuthenticated, currentPage, perPage, selectedAsset, selectedDomain, debouncedSearch]);

  // ================================================================
  // NEW: Comprehensive Filter Options Loading (Phase 1b Fix)
  // Reacts to selectedAsset changes for cascading domain filter
  // ================================================================

  const loadFilterOptions = useCallback(async () => {
    if (!isAuthenticated) return;
    
    try {
      const { apiClient } = await import('@/lib/api/client');
      
      // Build query params - include asset_id for cascading domain filter
      const params = new URLSearchParams();
      if (selectedAsset !== 'all') {
        params.append('asset_id', selectedAsset);
      }
      
      const url = `/api/v1/assets/filter-options${params.toString() ? `?${params.toString()}` : ''}`;
      const response = await apiClient.get(url);
      const filterData = response.data;
      
      // Set filter options - domains are now filtered by selected asset
      setAvailableDomains(filterData.domains || []);
      setAvailableAssets(filterData.assets || []);
      
    } catch (err) {
      console.error('Failed to load filter options:', err);
      // Don't show error toast for filter options - not critical
    }
  }, [isAuthenticated, selectedAsset]);

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Single useEffect for data loading (no conflicts)
  useEffect(() => {
    if (isAuthenticated) {
      loadSubdomains();
    }
  }, [isAuthenticated, loadSubdomains]);

  // Load comprehensive filter options once when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      loadFilterOptions();
    }
  }, [isAuthenticated, loadFilterOptions]);

  // ================================================================
  // NEW: Event Handlers (Update URL, Let useEffect Handle Loading)
  // ================================================================

  const handleSearchChange = (value: string) => {
    updateURL({ search: value, page: 1 }); // Reset to page 1 for new search
  };

  const handleFilterChange = (filterType: string, value: string) => {
    if (filterType === 'asset') {
      // When program changes, clear domain filter (it may not exist in new program)
      updateURL({ asset: value, parent_domain: null, page: 1 });
    } else {
      updateURL({ [filterType]: value, page: 1 }); // Reset to page 1 for new filter
    }
  };

  const handlePageChange = (newPage: number) => {
    updateURL({ page: newPage });
  };

  const handlePerPageChange = (newPerPage: number) => {
    updateURL({ per_page: newPerPage, page: 1 }); // Reset to page 1 for new page size
  };

  // ================================================================
  // NEW: Navigation & Utility Functions
  // ================================================================

  // Get current asset info for navigation context
  const currentAssetId = selectedAsset !== 'all' ? selectedAsset : null;
  const currentAssetName = availableAssets.find(asset => asset.id === currentAssetId)?.name;

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard!');
    } catch {
      toast.error('Failed to copy to clipboard');
    }
  };

  const copyAllVisibleSubdomains = async () => {
    if (!subdomainData?.subdomains.length) return;
    
    const subdomainList = subdomainData.subdomains.map(sub => sub.subdomain).join('\n');
    await copyToClipboard(subdomainList);
  };

  const handleExport = async (format: 'csv' | 'json') => {
    // Use backend streaming export with current filters
    await exportSubdomains(format, {
      asset_id: selectedAsset !== 'all' ? selectedAsset : undefined,
      parent_domain: selectedDomain !== 'all' ? selectedDomain : undefined,
    });
  };

  // ================================================================
  // NEW: Pagination Component
  // ================================================================

  const PaginationControls = () => {
    if (!subdomainData?.pagination || subdomainData.pagination.total_pages <= 1) return null;

    const { pagination } = subdomainData;
    
    return (
      <div className="flex items-center justify-between mt-6">
        <div className="text-sm text-muted-foreground">
          Showing {((pagination.page - 1) * pagination.per_page) + 1} to{' '}
          {Math.min(pagination.page * pagination.per_page, pagination.total)} of{' '}
          {pagination.total} subdomains
        </div>
        
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePageChange(pagination.page - 1)}
            disabled={!pagination.has_prev || isLoadingData}
          >
            <ChevronLeft className="h-4 w-4 mr-2" />
            Previous
          </Button>
          
          <div className="flex items-center space-x-1">
            {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
              const page = Math.max(1, pagination.page - 2) + i;
              if (page > pagination.total_pages) return null;
              
              return (
                <Button
                  key={page}
                  variant={page === pagination.page ? "default" : "outline"}
                  size="sm"
                  onClick={() => handlePageChange(page)}
                  disabled={isLoadingData}
                >
                  {page}
                </Button>
              );
            })}
          </div>
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePageChange(pagination.page + 1)}
            disabled={!pagination.has_next || isLoadingData}
          >
            Next
            <ChevronRight className="h-4 w-4 ml-2" />
          </Button>
        </div>
      </div>
    );
  };

  // ================================================================
  // Render Loading States
  // ================================================================

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  // ================================================================
  // NEW: Improved Main Render
  // ================================================================

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-6">
        {/* Header with Smart Navigation */}
        <div className="flex items-center justify-between">
          <div>
            {/* Dynamic Back Button */}
            {currentAssetId && currentAssetName ? (
              // When filtering by specific asset, show back to asset detail
              <div className="flex items-center space-x-2 mb-4">
                <Button 
                  variant="ghost" 
                  onClick={() => router.push(`/assets/${currentAssetId}`)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to {currentAssetName}
                </Button>
                <span className="text-muted-foreground">•</span>
                <Button 
                  variant="ghost" 
                  onClick={() => router.push('/dashboard')}
                  className="text-muted-foreground hover:text-foreground text-sm"
                >
                  Dashboard
                </Button>
              </div>
            ) : (
              // Default: back to dashboard
              <Button 
                variant="ghost" 
                onClick={() => router.push('/dashboard')}
                className="mb-4"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Dashboard
              </Button>
            )}

            <div className="flex items-center space-x-3">
              <Globe className="h-6 w-6 text-primary" />
              <h1 className="text-3xl font-bold tracking-tight">
                {currentAssetName ? `${currentAssetName} Subdomains` : 'Discovered Subdomains'}
                {subdomainData?.pagination.total && (
                  <span className="text-muted-foreground ml-2 text-2xl">
                    {subdomainData.pagination.total.toLocaleString()}
                  </span>
                )}
              </h1>
              {currentAssetId && (
                <Badge variant="secondary" className="px-2 py-1">
                  Asset Filter Active
                </Badge>
              )}
            </div>
            
            {/* Clean description - only show when filtering by specific asset */}
            {currentAssetName && (
              <p className="text-muted-foreground mt-2">
                Subdomains discovered for {currentAssetName}
              </p>
            )}
          </div>
        </div>

        {/* Enhanced Filters */}
        <Card className="border border-border bg-card">
          <CardHeader className="pb-4">
            <CardTitle className="text-base font-mono">filters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {/* Search */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Search
                </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    placeholder="search subdomains..."
                  value={searchTerm}
                  onChange={(e) => handleSearchChange(e.target.value)}
                    className="pl-10 font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors"
                />
                </div>
              </div>

              {/* Asset Filter */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Program
                </label>
              <Select value={selectedAsset} onValueChange={(value) => handleFilterChange('asset', value)}>
                  <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                    <SelectValue placeholder="all programs" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">all programs</SelectItem>
                  {availableAssets.map(asset => (
                    <SelectItem key={asset.id} value={asset.id}>{asset.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              </div>

              {/* Domain Filter */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Domain
                </label>
              <Select value={selectedDomain} onValueChange={(value) => handleFilterChange('parent_domain', value)}>
                  <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                    <SelectValue placeholder="all domains" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">all domains</SelectItem>
                  {availableDomains.map(domain => (
                    <SelectItem key={domain} value={domain}>{domain}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              </div>

              {/* Per Page */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Per Page
                </label>
              <Select value={perPage.toString()} onValueChange={(value) => handlePerPageChange(parseInt(value))}>
                  <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="10">10</SelectItem>
                    <SelectItem value="20">20</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                    <SelectItem value="100">100</SelectItem>
                    <SelectItem value="250">250</SelectItem>
                </SelectContent>
              </Select>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex space-x-2">
              <Button 
                onClick={copyAllVisibleSubdomains} 
                variant="outline"
                disabled={!subdomainData?.subdomains.length}
              >
                <Copy className="h-4 w-4 mr-2" />
                Copy Visible ({subdomainData?.subdomains.length || 0})
              </Button>
              <Button 
                onClick={() => handleExport('csv')} 
                variant="outline"
                className="font-mono"
              >
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
              <Button 
                onClick={() => handleExport('json')} 
                variant="outline"
                className="font-mono"
              >
                <FileText className="h-4 w-4 mr-2" />
                Export JSON
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Subdomains List */}
        <Card>
          <CardHeader>
            <CardTitle>
              Results
              {subdomainData?.pagination && (
                <span className="text-sm font-normal text-muted-foreground ml-2">
                  (Page {subdomainData.pagination.page} of {subdomainData.pagination.total_pages})
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="text-center py-8">
                <div className="text-red-500 mb-4">❌ {error}</div>
                <Button onClick={() => loadSubdomains()}>Try Again</Button>
              </div>
            ) : isLoadingData ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                <p className="text-muted-foreground mt-4">Loading subdomains...</p>
              </div>
            ) : !subdomainData?.subdomains.length ? (
              <div className="text-center py-8">
                <Globe className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-muted-foreground">No subdomains found</p>
                <p className="text-sm text-muted-foreground">
                  {searchTerm || selectedDomain !== 'all'
                    ? 'Try adjusting your filters' 
                    : 'Run your first scan to discover subdomains'
                  }
                </p>
              </div>
            ) : (
              <>
                <div className="space-y-3">
                  {subdomainData.subdomains.map((subdomain, index) => (
                    <div
                      key={`${subdomain.scan_job_id}-${index}`}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer"
                      onClick={() => copyToClipboard(subdomain.subdomain)}
                    >
                      <div className="flex-1 space-y-2">
                        {/* Row 1: Subdomain name and badges */}
                        <div className="flex items-center space-x-3">
                          <div className="font-mono text-sm font-medium">
                            {subdomain.subdomain}
                          </div>
                          <Badge variant="outline">{subdomain.parent_domain}</Badge>
                          {subdomain.asset_name && (
                            <Badge variant="outline">{subdomain.asset_name}</Badge>
                          )}
                        </div>
                        
                        {/* Row 2: Discovered date */}
                        <div className="flex items-center space-x-1 text-xs text-muted-foreground">
                          <Calendar className="h-3 w-3" />
                          <span>
                            Discovered {new Date(subdomain.discovered_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      
                      {/* Copy button */}
                      <div className="flex items-center space-x-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(subdomain.subdomain);
                          }}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
                
                <PaginationControls />
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Loading component for Suspense fallback
function SubdomainsLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-6">
        <div className="h-8 bg-muted animate-pulse rounded w-1/4" />
        <div className="h-4 bg-muted animate-pulse rounded w-1/2" />
        <div className="h-64 bg-muted animate-pulse rounded" />
      </div>
    </div>
  );
}

// Main page component with Suspense boundary
export default function SubdomainsPage() {
  return (
    <Suspense fallback={<SubdomainsLoading />}>
      <SubdomainsContent />
    </Suspense>
  );
}
