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

// HTTP Probes API and Types
import { fetchHTTPProbes, fetchHTTPProbeStats } from '@/lib/api/http-probes';
import type { HTTPProbe, HTTPProbeStats } from '@/types/http-probes';

// HTTP Probes Components
import {
  StatusCodeBadge,
  TechnologyList,
  RedirectChainIndicator,
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
  const technologyParam = searchParams.get('technology');
  const searchQuery = searchParams.get('search') || '';

  // Component state
  const [probes, setProbes] = useState<HTTPProbe[]>([]);
  const [stats, setStats] = useState<HTTPProbeStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
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
          technology?: string;
        } = {
          limit: perPage,
          offset,
        };

        if (assetIdParam) queryParams.asset_id = assetIdParam;
        if (statusCodeParam) queryParams.status_code = parseInt(statusCodeParam);
        if (technologyParam) queryParams.technology = technologyParam;

        // Fetch probes (now returns { probes, total, limit, offset })
        const response = await fetchHTTPProbes(queryParams);
        const probesData = response.probes || [];

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
        // Use total from API response for accurate pagination
        setTotalProbes(searchQuery ? filteredProbes.length : response.total);
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
    technologyParam,
    searchQuery,
  ]);

  // ================================================================
  // Fetch Statistics
  // ================================================================

  useEffect(() => {
    const fetchStats = async () => {
      if (!isAuthenticated) return;

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
      <div className="flex items-center space-x-3">
        <h1 className="text-2xl font-bold tracking-tight font-mono text-foreground">
          servers
        </h1>
        {stats && (
          <span className="text-muted-foreground text-xl font-mono">
            {stats.total_probes.toLocaleString()}
          </span>
        )}
      </div>

      {/* Filters */}
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
                placeholder="search by URL, subdomain, title, or server..."
                value={searchQuery}
                onChange={(e) => updateURLParams({ search: e.target.value })}
                className="pl-10 font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors"
              />
            </div>
          </div>

          {/* Filter Row */}
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

            {/* Status Code Filter */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Status
              </label>
              <Select
                value={statusCodeParam || 'all'}
                onValueChange={(value) =>
                  updateURLParams({ status_code: value === 'all' ? null : value })
                }
              >
                <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                  <SelectValue placeholder="all status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all status</SelectItem>
                  <SelectItem value="200">200 (OK)</SelectItem>
                  <SelectItem value="301">301 (Redirect)</SelectItem>
                  <SelectItem value="302">302 (Found)</SelectItem>
                  <SelectItem value="403">403 (Forbidden)</SelectItem>
                  <SelectItem value="404">404 (Not Found)</SelectItem>
                  <SelectItem value="500">500 (Error)</SelectItem>
                  <SelectItem value="502">502 (Bad Gateway)</SelectItem>
                  <SelectItem value="503">503 (Unavailable)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Technology Filter */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Technology
              </label>
              <Select
                value={technologyParam || 'all'}
                onValueChange={(value) =>
                  updateURLParams({ technology: value === 'all' ? null : value })
                }
              >
                <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                  <SelectValue placeholder="all tech" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all tech</SelectItem>
                  {availableTechnologies.slice(0, 20).map((tech) => (
                    <SelectItem key={tech} value={tech}>
                      {tech}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Per Page Selector */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Per Page
              </label>
              <Select
                value={String(perPage)}
                onValueChange={(value) =>
                  updateURLParams({ per_page: value, page: '1' })
                }
              >
                <SelectTrigger className="font-mono bg-background border-border hover:border-[--terminal-green]/50 focus:border-[--terminal-green] transition-colors">
                  <SelectValue placeholder="100" />
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

          {/* Clear Filters Button */}
          {(assetIdParam || statusCodeParam || technologyParam || searchQuery) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                updateURLParams({
                  asset_id: null,
                  status_code: null,
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
