'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Search, 
  Link2, 
  Copy, 
  ExternalLink, 
  ChevronLeft, 
  ChevronRight
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

// URLs API and Types
import { fetchURLs, fetchURLStats } from '@/lib/api/urls';
import type { URLRecord, URLStats } from '@/types/urls';

// Assets API
import { assetAPI } from '@/lib/api/assets';

// ================================================================
// Types and Interfaces
// ================================================================

interface Asset {
  id: string;
  name: string;
  description?: string;
}

// ================================================================
// Status Badge Component
// ================================================================

function StatusCodeBadge({ statusCode }: { statusCode: number | null }) {
  if (!statusCode) {
    return <Badge variant="outline" className="text-muted-foreground font-mono text-xs">—</Badge>;
  }
  
  const getVariant = (code: number) => {
    if (code >= 200 && code < 300) return 'default';
    if (code >= 300 && code < 400) return 'secondary';
    if (code >= 400 && code < 500) return 'destructive';
    return 'outline';
  };
  
  return (
    <Badge variant={getVariant(statusCode)} className="font-mono text-xs">
      {statusCode}
    </Badge>
  );
}

// ================================================================
// Loading Component
// ================================================================

function URLsLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  );
}

// ================================================================
// Main Component
// ================================================================

function URLsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // URL-driven state (single source of truth)
  const page = parseInt(searchParams.get('page') || '1', 10);
  const perPage = parseInt(searchParams.get('per_page') || '100', 10);
  const assetIdParam = searchParams.get('asset_id');
  const isAliveParam = searchParams.get('is_alive');
  const statusCodeParam = searchParams.get('status_code');
  const sourceParam = searchParams.get('source');
  const searchQuery = searchParams.get('search') || '';

  // Component state
  const [urls, setURLs] = useState<URLRecord[]>([]);
  const [stats, setStats] = useState<URLStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalURLs, setTotalURLs] = useState(0);

  // Filter options state
  const [availableAssets, setAvailableAssets] = useState<Asset[]>([]);

  // ================================================================
  // Update URL Parameters (Single Source of Truth)
  // ================================================================

  const updateURLParams = (updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());

    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === '') {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });

    // Reset to page 1 when filters change (except when page itself changes)
    if (!('page' in updates)) {
      params.set('page', '1');
    }

    router.push(`/urls?${params.toString()}`);
  };

  // ================================================================
  // Fetch Available Assets
  // ================================================================

  useEffect(() => {
    const fetchAssets = async () => {
      try {
        const assetsData = await assetAPI.getAssets();
        setAvailableAssets(assetsData);
      } catch (err) {
        console.error('Error fetching assets:', err);
      }
    };

    if (isAuthenticated) {
      fetchAssets();
    }
  }, [isAuthenticated]);

  // ================================================================
  // Fetch URLs Data
  // ================================================================

  useEffect(() => {
    const fetchData = async () => {
      if (!isAuthenticated) return;

      setIsLoading(true);
      setError(null);

      try {
        const offset = (page - 1) * perPage;

        // Build query parameters
        const queryParams: {
          limit: number;
          offset: number;
          asset_id?: string;
          is_alive?: boolean;
          status_code?: number;
          source?: string;
          search?: string;
        } = {
          limit: perPage,
          offset,
        };

        if (assetIdParam) queryParams.asset_id = assetIdParam;
        if (isAliveParam) queryParams.is_alive = isAliveParam === 'true';
        if (statusCodeParam) queryParams.status_code = parseInt(statusCodeParam);
        if (sourceParam) queryParams.source = sourceParam;
        if (searchQuery) queryParams.search = searchQuery;

        // Fetch URLs
        const urlsData = await fetchURLs(queryParams);

        setURLs(urlsData);
        setTotalURLs(urlsData.length);
      } catch (err) {
        console.error('Error fetching URLs:', err);
        setError('Failed to load URLs. Please try again.');
        toast.error('Failed to load URLs');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [
    isAuthenticated,
    page,
    perPage,
    assetIdParam,
    isAliveParam,
    statusCodeParam,
    sourceParam,
    searchQuery,
  ]);

  // ================================================================
  // Fetch Statistics (for total count in header)
  // ================================================================

  useEffect(() => {
    const fetchStats = async () => {
      if (!isAuthenticated) return;

      try {
        const statsParams: { asset_id?: string } = {};
        if (assetIdParam) statsParams.asset_id = assetIdParam;

        const statsData = await fetchURLStats(statsParams);
        setStats(statsData);
      } catch (err) {
        console.error('Error fetching URL stats:', err);
      }
    };

    fetchStats();
  }, [isAuthenticated, assetIdParam]);

  // ================================================================
  // Auth Redirect
  // ================================================================

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [isAuthenticated, authLoading, router]);

  if (authLoading) {
    return <URLsLoading />;
  }

  if (!isAuthenticated) {
    return null;
  }

  // ================================================================
  // Pagination Calculations
  // ================================================================

  const totalPages = Math.ceil(totalURLs / perPage);
  const hasNextPage = page < totalPages;
  const hasPrevPage = page > 1;

  // ================================================================
  // Helper Functions
  // ================================================================

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard!');
  };

  const openURL = (url: string) => {
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  // ================================================================
  // Render
  // ================================================================

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header - Minimalistic like /probes */}
      <div className="flex items-center space-x-3">
        <h1 className="text-2xl font-bold tracking-tight font-mono text-foreground">
          urls
        </h1>
        {stats && (
          <span className="text-muted-foreground text-xl font-mono">
            {stats.total_urls.toLocaleString()}
          </span>
        )}
      </div>

      {/* Filters - Styled like /probes */}
      <Card className="border border-border bg-card">
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-mono">filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Search */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="search by URL, domain, or title..."
                value={searchQuery}
                onChange={(e) => updateURLParams({ search: e.target.value })}
                className="pl-10 font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors"
              />
            </div>
          </div>

          {/* Filter Row - 4 columns like /probes */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Asset Filter */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Program
              </label>
              <Select
                value={assetIdParam || 'all'}
                onValueChange={(value) =>
                  updateURLParams({ asset_id: value === 'all' ? null : value })
                }
              >
                <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                  <SelectValue placeholder="all programs" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all programs</SelectItem>
                  {availableAssets.map((asset) => (
                    <SelectItem key={asset.id} value={asset.id}>
                      {asset.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Alive Status Filter */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Status
              </label>
              <Select
                value={isAliveParam || 'all'}
                onValueChange={(value) =>
                  updateURLParams({ is_alive: value === 'all' ? null : value })
                }
              >
                <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                  <SelectValue placeholder="all status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all status</SelectItem>
                  <SelectItem value="true">alive</SelectItem>
                  <SelectItem value="false">dead</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Status Code Filter */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                HTTP Code
              </label>
              <Select
                value={statusCodeParam || 'all'}
                onValueChange={(value) =>
                  updateURLParams({ status_code: value === 'all' ? null : value })
                }
              >
                <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                  <SelectValue placeholder="all codes" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all codes</SelectItem>
                  <SelectItem value="200">200 (OK)</SelectItem>
                  <SelectItem value="301">301 (Redirect)</SelectItem>
                  <SelectItem value="302">302 (Found)</SelectItem>
                  <SelectItem value="403">403 (Forbidden)</SelectItem>
                  <SelectItem value="404">404 (Not Found)</SelectItem>
                  <SelectItem value="500">500 (Error)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Source Filter */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Source
              </label>
              <Select
                value={sourceParam || 'all'}
                onValueChange={(value) =>
                  updateURLParams({ source: value === 'all' ? null : value })
                }
              >
                <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                  <SelectValue placeholder="all sources" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all sources</SelectItem>
                  <SelectItem value="katana">katana</SelectItem>
                  <SelectItem value="waymore">waymore</SelectItem>
                  <SelectItem value="gau">gau</SelectItem>
                  <SelectItem value="httpx">httpx</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Clear Filters Button */}
          {(assetIdParam || isAliveParam || statusCodeParam || sourceParam || searchQuery) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                updateURLParams({
                  asset_id: null,
                  is_alive: null,
                  status_code: null,
                  source: null,
                  search: null,
                })
              }
            >
              Clear All Filters
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {error ? (
        <div className="text-center py-12">
          <p className="text-red-500">{error}</p>
        </div>
      ) : isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="text-muted-foreground mt-4">Loading URLs...</p>
        </div>
      ) : urls.length === 0 ? (
        <div className="text-center py-12">
          <Link2 className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
          <h3 className="mt-4 text-lg font-semibold">No URLs found</h3>
          <p className="text-muted-foreground mt-2">
            {searchQuery || assetIdParam || statusCodeParam
              ? 'Try adjusting your filters or search query'
              : 'Run a Katana scan to discover URLs'}
          </p>
        </div>
      ) : (
        <>
          {/* URLs List - Clean like /probes */}
          <div className="space-y-4">
            {urls.map((urlRecord) => (
              <Card key={urlRecord.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-2">
                      {/* URL */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="text-base font-mono font-semibold bg-muted px-2 py-1 rounded break-all">
                          {urlRecord.url}
                        </code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(urlRecord.url)}
                          className="h-6 w-6 p-0"
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                        {urlRecord.is_alive && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openURL(urlRecord.url)}
                            className="h-6 w-6 p-0"
                          >
                            <ExternalLink className="h-3 w-3" />
                          </Button>
                        )}
                      </div>

                      {/* Metadata - Simplified */}
                      <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                        <span>{urlRecord.domain}</span>
                        {urlRecord.file_extension && (
                          <Badge variant="outline" className="text-xs font-mono">
                            .{urlRecord.file_extension}
                          </Badge>
                        )}
                        {urlRecord.has_params && (
                          <Badge variant="outline" className="text-xs font-mono">
                            params
                          </Badge>
                        )}
                        <span>
                          {formatDistanceToNow(new Date(urlRecord.first_discovered_at), {
                            addSuffix: true,
                          })}
                        </span>
                      </div>
                    </div>

                    {/* Status Badge - Simplified */}
                    <div className="flex items-center gap-2">
                      {urlRecord.is_alive !== null && (
                        <Badge 
                          variant="outline" 
                          className={`text-xs font-mono ${
                            urlRecord.is_alive 
                              ? 'text-green-500 border-green-500/30' 
                              : 'text-red-500 border-red-500/30'
                          }`}
                        >
                          {urlRecord.is_alive ? 'alive' : 'dead'}
                        </Badge>
                      )}
                      <StatusCodeBadge statusCode={urlRecord.status_code} />
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="space-y-3">
                  {/* Title */}
                  {urlRecord.title && (
                    <div>
                      <span className="text-xs text-muted-foreground font-semibold">Title: </span>
                      <span className="text-sm">{urlRecord.title}</span>
                    </div>
                  )}

                  {/* Server & Response - Clean */}
                  {(urlRecord.webserver || urlRecord.content_type) && (
                    <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                      {urlRecord.webserver && (
                        <span>
                          <span className="font-semibold">Server:</span>{' '}
                          <code className="font-mono bg-muted px-1 rounded">{urlRecord.webserver}</code>
                        </span>
                      )}
                      {urlRecord.content_type && (
                        <span>
                          <span className="font-semibold">Type:</span>{' '}
                          <code className="font-mono bg-muted px-1 rounded">{urlRecord.content_type}</code>
                        </span>
                      )}
                      {urlRecord.response_time_ms && (
                        <span className="font-mono">{urlRecord.response_time_ms}ms</span>
                      )}
                    </div>
                  )}

                  {/* Technologies - Simplified */}
                  {urlRecord.technologies && urlRecord.technologies.length > 0 && (
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-muted-foreground font-semibold">Tech:</span>
                      {urlRecord.technologies.slice(0, 6).map((tech) => (
                        <Badge key={tech} variant="secondary" className="text-xs font-mono">
                          {tech}
                        </Badge>
                      ))}
                      {urlRecord.technologies.length > 6 && (
                        <Badge variant="outline" className="text-xs font-mono">
                          +{urlRecord.technologies.length - 6}
                        </Badge>
                      )}
                    </div>
                  )}

                  {/* Final URL (if redirected) */}
                  {urlRecord.final_url && urlRecord.final_url !== urlRecord.url && (
                    <div className="text-xs">
                      <span className="text-muted-foreground font-semibold">Final: </span>
                      <code className="font-mono text-foreground break-all">
                        {urlRecord.final_url}
                      </code>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Showing {Math.min((page - 1) * perPage + 1, totalURLs)} to{' '}
              {Math.min(page * perPage, totalURLs)} of {totalURLs} URLs
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => updateURLParams({ page: String(page - 1) })}
                disabled={!hasPrevPage}
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>

              <div className="text-sm text-muted-foreground">
                Page {page} of {totalPages || 1}
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={() => updateURLParams({ page: String(page + 1) })}
                disabled={!hasNextPage}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ================================================================
// Page Export with Suspense
// ================================================================

export default function URLsPage() {
  return (
    <Suspense fallback={<URLsLoading />}>
      <URLsPageContent />
    </Suspense>
  );
}
