'use client';

/**
 * Programs Page - NeoBot-Net LEAN
 * 
 * Displays all bug bounty programs with reconnaissance data.
 * Read-only view - programs are managed via CLI by the operator.
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { 
  Building2, 
  Globe, 
  Search, 
  ExternalLink,
  Calendar,
  Radar
} from 'lucide-react';
import Link from 'next/link';
import { reconDataService, type ReconAsset, type ReconSummary } from '@/lib/api/recon-data';
import { toast } from 'sonner';

export default function ProgramsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  
  const [programs, setPrograms] = useState<ReconAsset[]>([]);
  const [filteredPrograms, setFilteredPrograms] = useState<ReconAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [stats, setStats] = useState<ReconSummary>({
    total_assets: 0,
    active_assets: 0,
    total_domains: 0,
    active_domains: 0,
    total_scans: 0,
    completed_scans: 0,
    failed_scans: 0,
    pending_scans: 0,
    total_subdomains: 0
  });

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Load programs
  const loadPrograms = async () => {
    try {
      setLoading(true);
      const { assets, summary } = await reconDataService.getAssetsData();
      setPrograms(assets);
      setFilteredPrograms(assets);
      setStats(summary);
    } catch (error) {
      console.error('Failed to load programs:', error);
      toast.error('Failed to load programs');
      setPrograms([]);
      setFilteredPrograms([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadPrograms();
    }
  }, [isAuthenticated]);

  // Filter programs by search term
  useEffect(() => {
    if (!searchTerm.trim()) {
      setFilteredPrograms(programs);
    } else {
      const term = searchTerm.toLowerCase();
      setFilteredPrograms(
        programs.filter(p => 
          p.name.toLowerCase().includes(term) ||
          p.description?.toLowerCase().includes(term) ||
          p.tags?.some(t => t.toLowerCase().includes(term))
        )
      );
    }
  }, [searchTerm, programs]);

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <Building2 className="h-8 w-8 text-primary" />
              Bug Bounty Programs
            </h1>
            <p className="text-muted-foreground mt-2">
              Browse reconnaissance data for all tracked programs
            </p>
          </div>
          
          {/* Search */}
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search programs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Programs</CardTitle>
              <Building2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_assets}</div>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Domains</CardTitle>
              <Globe className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_domains}</div>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Subdomains</CardTitle>
              <Search className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_subdomains.toLocaleString()}</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Scans</CardTitle>
              <Radar className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_scans}</div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Programs Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {loading ? (
            // Skeleton loaders
            [...Array(6)].map((_, i) => (
              <Card key={`skeleton-${i}`} className="border">
                <CardContent className="p-6">
                  <div className="h-6 bg-muted animate-pulse rounded w-3/4 mb-4" />
                  <div className="h-4 bg-muted animate-pulse rounded w-full mb-2" />
                  <div className="grid grid-cols-2 gap-4 mt-4">
                    <div className="h-12 bg-muted animate-pulse rounded" />
                    <div className="h-12 bg-muted animate-pulse rounded" />
                  </div>
                </CardContent>
              </Card>
            ))
          ) : filteredPrograms.length === 0 ? (
            <Card className="col-span-full">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">
                  {searchTerm ? 'No programs found' : 'No programs yet'}
                </h3>
                <p className="text-muted-foreground text-center">
                  {searchTerm 
                    ? 'Try adjusting your search term' 
                    : 'Programs are added by the operator via CLI'
                  }
                </p>
              </CardContent>
            </Card>
          ) : (
            filteredPrograms.map((program) => (
              <Link key={program.id} href={`/programs/${program.id}`}>
                <Card className="hover:shadow-lg transition-all duration-200 border hover:border-primary/30 cursor-pointer h-full">
                  <CardContent className="p-6">
                    {/* Program Name */}
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="text-lg font-semibold truncate flex-1" title={program.name}>
                        {program.name}
                      </h3>
                      {program.bug_bounty_url && (
                        <ExternalLink className="h-4 w-4 text-muted-foreground flex-shrink-0 ml-2" />
                      )}
                    </div>

                    {/* Description */}
                    {program.description && (
                      <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                        {program.description}
                      </p>
                    )}

                    {/* Tags */}
                    {program.tags && program.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-4">
                        {program.tags.slice(0, 3).map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                        {program.tags.length > 3 && (
                          <Badge variant="outline" className="text-xs">
                            +{program.tags.length - 3}
                          </Badge>
                        )}
                      </div>
                    )}

                    {/* Stats */}
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <div className="text-2xl font-bold">{program.apex_domain_count || 0}</div>
                        <div className="text-xs text-muted-foreground">Domains</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold">{(program.total_subdomains || 0).toLocaleString()}</div>
                        <div className="text-xs text-muted-foreground">Subdomains</div>
                      </div>
                    </div>

                    {/* Last Scan Date */}
                    <div className="flex items-center text-sm text-muted-foreground">
                      <Calendar className="h-4 w-4 mr-2" />
                      {program.last_scan_date ? (
                        <span>
                          Last scanned {new Date(program.last_scan_date).toLocaleDateString()}
                        </span>
                      ) : (
                        <span>No scans yet</span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

