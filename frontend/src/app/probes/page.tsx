'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Search, 
  Globe, 
  Copy, 
  ExternalLink, 
  ChevronLeft, 
  ChevronRight,
  Filter,
  Network
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

// HTTP Probes API and Types
import { fetchHTTPProbes, fetchHTTPProbeStats } from '@/lib/api/http-probes';
import type { HTTPProbe, HTTPProbeStats } from '@/types/http-probes';

// HTTP Probes Components
import {
  StatusCodeBadge,
  TechnologyList,
  RedirectChainIndicator,
  HTTPProbeStatsCards,
} from '@/components/http-probes';

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
// Loading Component
// ================================================================

function ProbesLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  );
}

// ================================================================
// Main Component
// ================================================================

function ProbesPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // URL-driven state (single source of truth)
  const page = parseInt(searchParams.get('page') || '1', 10);
  const perPage = parseInt(searchParams.get('per_page') || '100', 10);
  const assetIdParam = searchParams.get('asset_id');
  const statusCodeParam = searchParams.get('status_code');
  const schemeParam = searchParams.get('scheme') as 'http' | 'https' | null;
  const technologyParam = searchParams.get('technology');
  const searchQuery = searchParams.get('search') || '';

  // Component state
  const [probes, setProbes] = useState<HTTPProbe[]>([]);
  const [stats, setStats] = useState<HTTPProbeStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalProbes, setTotalProbes] = useState(0);

  // Filter options state
  const [availableAssets, setAvailableAssets] = useState<Asset[]>([]);
  const [availableTechnologies, setAvailableTechnologies] = useState<string[]>([]);

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

    router.push(`/probes?${params.toString()}`);
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
  // Fetch HTTP Probes Data
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
          status_code?: number;
          scheme?: 'http' | 'https';
          technology?: string;
        } = {
          limit: perPage,
          offset,
        };

        if (assetIdParam) queryParams.asset_id = assetIdParam;
        if (statusCodeParam) queryParams.status_code = parseInt(statusCodeParam);
        if (schemeParam) queryParams.scheme = schemeParam;
        if (technologyParam) queryParams.technology = technologyParam;

        // Fetch probes
        const probesData = await fetchHTTPProbes(queryParams);

        // Filter by search query (client-side for now)
        let filteredProbes = probesData;
        if (searchQuery) {
          const query = searchQuery.toLowerCase();
          filteredProbes = probesData.filter(
            (probe) =>
              probe.url.toLowerCase().includes(query) ||
              probe.subdomain.toLowerCase().includes(query) ||
              probe.title?.toLowerCase().includes(query) ||
              probe.webserver?.toLowerCase().includes(query)
          );
        }

        setProbes(filteredProbes);
        setTotalProbes(filteredProbes.length); // Note: This is approximate for pagination
      } catch (err) {
        console.error('Error fetching HTTP probes:', err);
        setError('Failed to load HTTP probes. Please try again.');
        toast.error('Failed to load HTTP probes');
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
    statusCodeParam,
    schemeParam,
    technologyParam,
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

        const statsData = await fetchHTTPProbeStats(statsParams);
        setStats(statsData);

        // Populate technology dropdown from stats (always shows ALL technologies)
        // This ensures the dropdown options don't change when filters are applied
        if (statsData.top_technologies.length > 0) {
          const allTechs = statsData.top_technologies.map((t) => t.name).sort();
          setAvailableTechnologies(allTechs);
        }
      } catch (err) {
        console.error('Error fetching HTTP probe stats:', err);
        // Don't show error toast for stats, it's non-critical
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
    return <ProbesLoading />;
  }

  if (!isAuthenticated) {
    return null;
  }

  // ================================================================
  // Pagination Calculations
  // ================================================================

  const totalPages = Math.ceil(totalProbes / perPage);
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
          <Network className="h-6 w-6 text-primary" />
          <h1 className="text-3xl font-bold tracking-tight">
            HTTP Probes
            {stats && (
              <span className="text-muted-foreground ml-2 text-2xl">
                {stats.total_probes.toLocaleString()}
              </span>
            )}
          </h1>
        </div>
        <p className="text-muted-foreground">
          Discovered HTTP endpoints with status codes, technologies, and server information
        </p>
      </div>

      {/* Statistics Cards */}
      {stats && (
        <HTTPProbeStatsCards stats={stats} loading={isLoadingStats} />
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
          <CardDescription>
            Filter and search HTTP probes
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search by URL, subdomain, title, or server..."
              value={searchQuery}
              onChange={(e) => updateURLParams({ search: e.target.value })}
              className="pl-10"
            />
          </div>

          {/* Filter Row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
                <SelectItem value="301">301 (Moved Permanently)</SelectItem>
                <SelectItem value="302">302 (Found)</SelectItem>
                <SelectItem value="403">403 (Forbidden)</SelectItem>
                <SelectItem value="404">404 (Not Found)</SelectItem>
                <SelectItem value="500">500 (Server Error)</SelectItem>
                <SelectItem value="502">502 (Bad Gateway)</SelectItem>
                <SelectItem value="503">503 (Service Unavailable)</SelectItem>
              </SelectContent>
            </Select>

            {/* Scheme Filter */}
            <Select
              value={schemeParam || 'all'}
              onValueChange={(value) =>
                updateURLParams({ scheme: value === 'all' ? null : value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All Schemes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Schemes</SelectItem>
                <SelectItem value="https">HTTPS</SelectItem>
                <SelectItem value="http">HTTP</SelectItem>
              </SelectContent>
            </Select>

            {/* Technology Filter */}
            <Select
              value={technologyParam || 'all'}
              onValueChange={(value) =>
                updateURLParams({ technology: value === 'all' ? null : value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All Technologies" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Technologies</SelectItem>
                {availableTechnologies.slice(0, 20).map((tech) => (
                  <SelectItem key={tech} value={tech}>
                    {tech}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Clear Filters Button */}
          {(assetIdParam || statusCodeParam || schemeParam || technologyParam || searchQuery) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                updateURLParams({
                  asset_id: null,
                  status_code: null,
                  scheme: null,
                  technology: null,
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
          <p className="text-muted-foreground mt-4">Loading HTTP probes...</p>
        </div>
      ) : probes.length === 0 ? (
        <div className="text-center py-12">
          <Globe className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
          <h3 className="mt-4 text-lg font-semibold">No HTTP probes found</h3>
          <p className="text-muted-foreground mt-2">
            {searchQuery || assetIdParam || statusCodeParam
              ? 'Try adjusting your filters or search query'
              : 'Start a scan to discover HTTP endpoints'}
          </p>
        </div>
      ) : (
        <>
          {/* Probes List */}
          <div className="space-y-4">
            {probes.map((probe) => (
              <Card key={probe.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-2">
                      {/* URL */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="text-base font-mono font-semibold bg-muted px-2 py-1 rounded">
                          {probe.url}
                        </code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(probe.url)}
                          className="h-6 w-6 p-0"
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openURL(probe.url)}
                          className="h-6 w-6 p-0"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </Button>
                      </div>

                      {/* Metadata */}
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          {probe.subdomain}
                        </span>
                        {probe.ip && (
                          <span className="font-mono">{probe.ip}</span>
                        )}
                        <span>
                          {formatDistanceToNow(new Date(probe.created_at), {
                            addSuffix: true,
                          })}
                        </span>
                      </div>
                    </div>

                    {/* Status Code */}
                    <StatusCodeBadge statusCode={probe.status_code} />
                  </div>
                </CardHeader>

                <CardContent className="space-y-3">
                  {/* Title */}
                  {probe.title && (
                    <div>
                      <span className="text-xs text-muted-foreground font-semibold">Title: </span>
                      <span className="text-sm">{probe.title}</span>
                    </div>
                  )}

                  {/* Server */}
                  {probe.webserver && (
                    <div>
                      <span className="text-xs text-muted-foreground font-semibold">Server: </span>
                      <code className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded">
                        {probe.webserver}
                      </code>
                    </div>
                  )}

                  {/* Content Info */}
                  {(probe.content_type || probe.content_length) && (
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      {probe.content_type && (
                        <span className="font-mono">{probe.content_type}</span>
                      )}
                      {probe.content_length && (
                        <span className="font-mono">
                          {(probe.content_length / 1024).toFixed(2)} KB
                        </span>
                      )}
                    </div>
                  )}

                  {/* Technologies */}
                  {probe.technologies.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground font-semibold">
                        Technologies:
                      </span>
                      <TechnologyList technologies={probe.technologies} limit={8} />
                    </div>
                  )}

                  {/* CDN */}
                  {probe.cdn_name && (
                    <div>
                      <span className="text-xs text-muted-foreground font-semibold">CDN: </span>
                      <Badge variant="secondary" className="text-xs">
                        {probe.cdn_name}
                      </Badge>
                    </div>
                  )}

                  {/* Redirect Chain */}
                  {probe.chain_status_codes.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground font-semibold">
                        Redirect Chain:
                      </span>
                      <RedirectChainIndicator chainStatusCodes={probe.chain_status_codes} />
                      {probe.final_url && probe.final_url !== probe.url && (
                        <div className="mt-2 text-xs">
                          <span className="text-muted-foreground">Final URL: </span>
                          <code className="font-mono text-foreground break-all">
                            {probe.final_url}
                          </code>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Showing {Math.min((page - 1) * perPage + 1, totalProbes)} to{' '}
              {Math.min(page * perPage, totalProbes)} of {totalProbes} probes
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
                Page {page} of {totalPages}
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

export default function ProbesPage() {
  return (
    <Suspense fallback={<ProbesLoading />}>
      <ProbesPageContent />
    </Suspense>
  );
}
