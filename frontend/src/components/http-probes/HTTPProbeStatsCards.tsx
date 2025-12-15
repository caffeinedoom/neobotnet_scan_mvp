import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Globe, Server, Layers, ArrowRight, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StatusCodeBadge } from './StatusCodeBadge';
import { TechnologyCountBadge } from './TechnologyBadge';
import type { HTTPProbeStats } from '@/types/http-probes';
import { cn } from '@/lib/utils';

interface HTTPProbeStatsCardsProps {
  stats: HTTPProbeStats;
  loading?: boolean;
  className?: string;
}

/**
 * HTTPProbeStatsCards Component
 * 
 * Displays HTTP probe statistics in elegant cards.
 * Shows total probes, status code distribution, top technologies, etc.
 */
export function HTTPProbeStatsCards({ 
  stats, 
  loading = false,
  className 
}: HTTPProbeStatsCardsProps) {
  // Collapsible sections state - all collapsed by default for clean look
  const [techExpanded, setTechExpanded] = useState(false);
  const [serversExpanded, setServersExpanded] = useState(false);
  const [cdnExpanded, setCdnExpanded] = useState(false);

  if (loading) {
    return (
      <div className={cn('grid gap-4 md:grid-cols-2 lg:grid-cols-4', className)}>
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader className="pb-3">
              <div className="h-4 bg-muted rounded w-24" />
            </CardHeader>
            <CardContent>
              <div className="h-8 bg-muted rounded w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const sortedStatusCodes = Object.entries(stats.status_code_distribution)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Probes */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Probes</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_probes.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground mt-1">
              HTTP endpoints discovered
            </p>
          </CardContent>
        </Card>

        {/* Status Codes */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Status Codes</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Object.keys(stats.status_code_distribution).length}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Unique response types
            </p>
          </CardContent>
        </Card>

        {/* Technologies */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Technologies</CardTitle>
            <Layers className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.top_technologies.length}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Tech stack detected
            </p>
          </CardContent>
        </Card>

        {/* Redirects */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Redirects</CardTitle>
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.redirect_chains_count}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Redirect chains found
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Stats - 2 Compact Cards */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Status Code Distribution */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Status Code Distribution</CardTitle>
            <CardDescription>HTTP response codes</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[200px] overflow-y-auto pr-2">
              {sortedStatusCodes.length === 0 ? (
                <p className="text-sm text-muted-foreground">No data available</p>
              ) : (
                sortedStatusCodes.map(([code, count]) => (
                  <div key={code} className="flex items-center justify-between">
                    <StatusCodeBadge statusCode={parseInt(code)} />
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-semibold">{count}</span>
                      <span className="text-xs text-muted-foreground">
                        ({((count / stats.total_probes) * 100).toFixed(1)}%)
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Technologies & Web Servers Combined */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Technologies & Web Servers</CardTitle>
            <CardDescription>Detected tech stack and server software</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-[200px] overflow-y-auto pr-2">
              {/* Technologies Section - Collapsible */}
              {stats.top_technologies.length > 0 && (
                <div className="space-y-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setTechExpanded(!techExpanded)}
                    className="w-full justify-between h-7 px-2 hover:bg-muted/50"
                  >
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      Technologies ({stats.top_technologies.length})
                    </span>
                    {techExpanded ? (
                      <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                  </Button>
                  {techExpanded && (
                    <div className="space-y-1.5 pl-2">
                      {stats.top_technologies.slice(0, 15).map((tech) => (
                        <TechnologyCountBadge
                          key={tech.name}
                          name={tech.name}
                          count={tech.count}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Web Servers Section - Collapsible */}
              {stats.top_servers.length > 0 && (
                <div className="space-y-2 pt-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setServersExpanded(!serversExpanded)}
                    className="w-full justify-between h-7 px-2 hover:bg-muted/50"
                  >
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      Web Servers ({stats.top_servers.length})
                    </span>
                    {serversExpanded ? (
                      <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                  </Button>
                  {serversExpanded && (
                    <div className="space-y-1.5 pl-2">
                      {stats.top_servers.slice(0, 10).map((server) => (
                        <div
                          key={server.name}
                          className="flex items-center justify-between gap-2"
                        >
                          <code className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded flex-1 truncate">
                            {server.name}
                          </code>
                          <span className="text-xs text-muted-foreground font-mono font-semibold shrink-0">
                            {server.count}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* CDN Section - Collapsible (if applicable) */}
              {Object.keys(stats.cdn_usage).length > 0 && (
                <div className="space-y-2 pt-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCdnExpanded(!cdnExpanded)}
                    className="w-full justify-between h-7 px-2 hover:bg-muted/50"
                  >
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      CDN Providers ({Object.keys(stats.cdn_usage).length})
                    </span>
                    {cdnExpanded ? (
                      <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                  </Button>
                  {cdnExpanded && (
                    <div className="space-y-1.5 pl-2">
                      {Object.entries(stats.cdn_usage)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 5)
                        .map(([cdn, count]) => (
                          <div
                            key={cdn}
                            className="flex items-center justify-between gap-2"
                          >
                            <span className="text-sm font-medium">{cdn}</span>
                            <span className="text-xs text-muted-foreground font-mono font-semibold">
                              {count}
                            </span>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )}

              {/* Empty State */}
              {stats.top_technologies.length === 0 && stats.top_servers.length === 0 && (
                <p className="text-sm text-muted-foreground">No data available</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
