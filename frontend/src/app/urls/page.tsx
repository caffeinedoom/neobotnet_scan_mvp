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
  ChevronRight,
  Filter,
  Globe,
  CheckCircle2,
  XCircle,
  Clock,
  FileCode
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
    return <Badge variant="outline" className="text-muted-foreground">Pending</Badge>;
  }
  
  const getVariant = (code: number) => {
    if (code >= 200 && code < 300) return 'default';
    if (code >= 300 && code < 400) return 'secondary';
    if (code >= 400 && code < 500) return 'destructive';
    return 'outline';
  };
  
  return (
    <Badge variant={getVariant(statusCode)} className="font-mono">
      {statusCode}
    </Badge>
  );
}

// ================================================================
// Alive Status Badge Component
// ================================================================

function AliveStatusBadge({ isAlive }: { isAlive: boolean | null }) {
  if (isAlive === null) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        <Clock className="w-3 h-3 mr-1" />
        Pending
      </Badge>
    );
  }
  
  if (isAlive) {
    return (
      <Badge className="bg-green-500/10 text-green-500 border-green-500/20">
        <CheckCircle2 className="w-3 h-3 mr-1" />
        Alive
      </Badge>
    );
  }
  
  return (
    <Badge variant="destructive" className="bg-red-500/10 text-red-500 border-red-500/20">
      <XCircle className="w-3 h-3 mr-1" />
      Dead
    </Badge>
  );
}

// ================================================================
// Source Badges Component
// ================================================================

function SourceBadges({ sources }: { sources: string[] }) {
  const sourceColors: Record<string, string> = {
    katana: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
    waymore: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
    gau: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
    httpx: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20',
  };
  
  return (
    <div className="flex flex-wrap gap-1">
      {sources.map((source) => (
        <Badge 
          key={source} 
          variant="outline" 
          className={`text-xs ${sourceColors[source.toLowerCase()] || ''}`}
        >
          {source}
        </Badge>
      ))}
    </div>
  );
}

// ================================================================
// Stats Cards Component
// ================================================================

function URLStatsCards({ stats, loading }: { stats: URLStats | null; loading: boolean }) {
  if (loading || !stats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {[...Array(6)].map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader className="pb-2">
              <div className="h-4 bg-muted rounded w-20" />
            </CardHeader>
            <CardContent>
              <div className="h-8 bg-muted rounded w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }
  
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="text-xs">Total URLs</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold font-mono">{stats.total_urls.toLocaleString()}</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="text-xs flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-green-500" />
            Alive
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold font-mono text-green-500">
            {stats.alive_urls.toLocaleString()}
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="text-xs flex items-center gap-1">
            <XCircle className="w-3 h-3 text-red-500" />
            Dead
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold font-mono text-red-500">
            {stats.dead_urls.toLocaleString()}
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="text-xs flex items-center gap-1">
            <Clock className="w-3 h-3 text-yellow-500" />
            Pending
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold font-mono text-yellow-500">
            {stats.pending_urls.toLocaleString()}
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="text-xs flex items-center gap-1">
            <FileCode className="w-3 h-3" />
            With Params
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold font-mono">{stats.urls_with_params.toLocaleString()}</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="text-xs flex items-center gap-1">
            <Globe className="w-3 h-3" />
            Unique Domains
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold font-mono">{stats.unique_domains.toLocaleString()}</div>
        </CardContent>
      </Card>
    </div>
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
  const hasParamsParam = searchParams.get('has_params');
  const searchQuery = searchParams.get('search') || '';

  // Component state
  const [urls, setURLs] = useState<URLRecord[]>([]);
  const [stats, setStats] = useState<URLStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
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
          has_params?: boolean;
          search?: string;
        } = {
          limit: perPage,
          offset,
        };

        if (assetIdParam) queryParams.asset_id = assetIdParam;
        if (isAliveParam) queryParams.is_alive = isAliveParam === 'true';
        if (statusCodeParam) queryParams.status_code = parseInt(statusCodeParam);
        if (sourceParam) queryParams.source = sourceParam;
        if (hasParamsParam) queryParams.has_params = hasParamsParam === 'true';
        if (searchQuery) queryParams.search = searchQuery;

        // Fetch URLs
        const urlsData = await fetchURLs(queryParams);

        setURLs(urlsData);
        setTotalURLs(urlsData.length); // Note: This is approximate for pagination
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
    hasParamsParam,
    searchQuery,
  ]);

  // ================================================================
  // Fetch Statistics
  // ================================================================

  useEffect(() => {
    const fetchStats = async () => {
      if (!isAuthenticated) return;

      setIsLoadingStats(true);

      try {
        const statsParams: { asset_id?: string } = {};
        if (assetIdParam) statsParams.asset_id = assetIdParam;

        const statsData = await fetchURLStats(statsParams);
        setStats(statsData);
      } catch (err) {
        console.error('Error fetching URL stats:', err);
      } finally {
        setIsLoadingStats(false);
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
      {/* Header */}
      <div className="flex flex-col space-y-2">
        <div className="flex items-center space-x-2">
          <Link2 className="h-6 w-6 text-primary" />
          <h1 className="text-3xl font-bold tracking-tight">
            URLs
            {stats && (
              <span className="text-muted-foreground ml-2 text-2xl">
                {stats.total_urls.toLocaleString()}
              </span>
            )}
          </h1>
        </div>
        <p className="text-muted-foreground">
          Discovered URLs from Katana, Waymore, GAU, and other sources. Probed and enriched by URL Resolver.
        </p>
      </div>

      {/* Statistics Cards */}
      <URLStatsCards stats={stats} loading={isLoadingStats} />

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
          <CardDescription>
            Filter and search discovered URLs
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search by URL, domain, or title..."
              value={searchQuery}
              onChange={(e) => updateURLParams({ search: e.target.value })}
              className="pl-10"
            />
          </div>

          {/* Filter Row */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* Asset Filter */}
            <Select
              value={assetIdParam || 'all'}
              onValueChange={(value) =>
                updateURLParams({ asset_id: value === 'all' ? null : value })
              }
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

            {/* Alive Status Filter */}
            <Select
              value={isAliveParam || 'all'}
              onValueChange={(value) =>
                updateURLParams({ is_alive: value === 'all' ? null : value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="true">Alive</SelectItem>
                <SelectItem value="false">Dead</SelectItem>
              </SelectContent>
            </Select>

            {/* Status Code Filter */}
            <Select
              value={statusCodeParam || 'all'}
              onValueChange={(value) =>
                updateURLParams({ status_code: value === 'all' ? null : value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All Status Codes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status Codes</SelectItem>
                <SelectItem value="200">200 (OK)</SelectItem>
                <SelectItem value="301">301 (Moved)</SelectItem>
                <SelectItem value="302">302 (Found)</SelectItem>
                <SelectItem value="403">403 (Forbidden)</SelectItem>
                <SelectItem value="404">404 (Not Found)</SelectItem>
                <SelectItem value="500">500 (Server Error)</SelectItem>
              </SelectContent>
            </Select>

            {/* Source Filter */}
            <Select
              value={sourceParam || 'all'}
              onValueChange={(value) =>
                updateURLParams({ source: value === 'all' ? null : value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All Sources" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sources</SelectItem>
                <SelectItem value="katana">Katana</SelectItem>
                <SelectItem value="waymore">Waymore</SelectItem>
                <SelectItem value="gau">GAU</SelectItem>
                <SelectItem value="httpx">HTTPx</SelectItem>
              </SelectContent>
            </Select>

            {/* Has Params Filter */}
            <Select
              value={hasParamsParam || 'all'}
              onValueChange={(value) =>
                updateURLParams({ has_params: value === 'all' ? null : value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All URLs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All URLs</SelectItem>
                <SelectItem value="true">With Parameters</SelectItem>
                <SelectItem value="false">Without Parameters</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Clear Filters Button */}
          {(assetIdParam || isAliveParam || statusCodeParam || sourceParam || hasParamsParam || searchQuery) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                updateURLParams({
                  asset_id: null,
                  is_alive: null,
                  status_code: null,
                  source: null,
                  has_params: null,
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
          {/* URLs List */}
          <div className="space-y-4">
            {urls.map((urlRecord) => (
              <Card key={urlRecord.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-2">
                      {/* URL */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="text-sm font-mono font-semibold bg-muted px-2 py-1 rounded break-all">
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

                      {/* Metadata */}
                      <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                        <span>{urlRecord.domain}</span>
                        {urlRecord.file_extension && (
                          <Badge variant="outline" className="text-xs">
                            .{urlRecord.file_extension}
                          </Badge>
                        )}
                        {urlRecord.has_params && (
                          <Badge variant="outline" className="text-xs">
                            <FileCode className="w-3 h-3 mr-1" />
                            Has Params
                          </Badge>
                        )}
                        <span>
                          {formatDistanceToNow(new Date(urlRecord.first_discovered_at), {
                            addSuffix: true,
                          })}
                        </span>
                      </div>
                    </div>

                    {/* Status Badges */}
                    <div className="flex items-center gap-2">
                      <AliveStatusBadge isAlive={urlRecord.is_alive} />
                      <StatusCodeBadge statusCode={urlRecord.status_code} />
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="space-y-3">
                  {/* Sources */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground font-semibold">Sources:</span>
                    <SourceBadges sources={urlRecord.sources} />
                  </div>

                  {/* Title */}
                  {urlRecord.title && (
                    <div>
                      <span className="text-xs text-muted-foreground font-semibold">Title: </span>
                      <span className="text-sm">{urlRecord.title}</span>
                    </div>
                  )}

                  {/* Server & Response */}
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
                      <span>
                        <span className="font-semibold">Response:</span>{' '}
                        {urlRecord.response_time_ms}ms
                      </span>
                    )}
                  </div>

                  {/* Technologies */}
                  {urlRecord.technologies && urlRecord.technologies.length > 0 && (
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-muted-foreground font-semibold">Tech:</span>
                      {urlRecord.technologies.slice(0, 6).map((tech) => (
                        <Badge key={tech} variant="secondary" className="text-xs">
                          {tech}
                        </Badge>
                      ))}
                      {urlRecord.technologies.length > 6 && (
                        <Badge variant="outline" className="text-xs">
                          +{urlRecord.technologies.length - 6} more
                        </Badge>
                      )}
                    </div>
                  )}

                  {/* Final URL (if redirected) */}
                  {urlRecord.final_url && urlRecord.final_url !== urlRecord.url && (
                    <div className="text-xs">
                      <span className="text-muted-foreground font-semibold">Final URL: </span>
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

