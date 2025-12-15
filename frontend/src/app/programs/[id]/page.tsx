'use client';

/**
 * Program Detail Page - NeoBot-Net LEAN
 * 
 * Displays detailed reconnaissance data for a specific program.
 * Read-only view with links to subdomains, DNS, and HTTP probes.
 */

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  ArrowLeft,
  Globe, 
  Search, 
  ExternalLink,
  Calendar,
  Database,
  Wifi,
  Radar,
  Clock
} from 'lucide-react';
import Link from 'next/link';
import { reconDataService, type ReconAsset } from '@/lib/api/recon-data';
import { toast } from 'sonner';

export default function ProgramDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { isAuthenticated, isLoading } = useAuth();
  
  const [program, setProgram] = useState<ReconAsset | null>(null);
  const [loading, setLoading] = useState(true);

  const programId = params.id as string;

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Load program details
  const loadProgram = async () => {
    try {
      setLoading(true);
      const programData = await reconDataService.getAssetDetailData(programId);
      
      if (!programData) {
        toast.error('Program not found');
        router.push('/programs');
        return;
      }
      
      setProgram(programData);
    } catch (error) {
      console.error('Failed to load program:', error);
      toast.error('Failed to load program');
      router.push('/programs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated && programId) {
      loadProgram();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, programId]);

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          <div className="h-8 bg-muted animate-pulse rounded w-1/4" />
          <div className="h-4 bg-muted animate-pulse rounded w-1/2" />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-muted animate-pulse rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!program) {
    return null;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-6">
        {/* Back Button */}
        <Button 
          variant="ghost" 
          onClick={() => router.push('/programs')}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Programs
        </Button>

        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              {program.name}
              {program.bug_bounty_url && (
                <a 
                  href={program.bug_bounty_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-primary hover:text-primary/80"
                >
                  <ExternalLink className="h-6 w-6" />
                </a>
              )}
            </h1>
            {program.description && (
              <p className="text-muted-foreground mt-2 max-w-2xl">
                {program.description}
              </p>
            )}
            
            {/* Tags */}
            {program.tags && program.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-4">
                {program.tags.map((tag) => (
                  <Badge key={tag} variant="secondary">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Last Scan Info */}
          <Card className="w-full sm:w-auto">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-sm">
                <Clock className="h-4 w-4 text-muted-foreground" />
                {program.last_scan_date ? (
                  <span>
                    Last scanned: <strong>{new Date(program.last_scan_date).toLocaleDateString()}</strong>
                  </span>
                ) : (
                  <span className="text-muted-foreground">No scans yet</span>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Domains</CardTitle>
              <Globe className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{program.apex_domain_count || 0}</div>
              <p className="text-xs text-muted-foreground">
                {program.active_domain_count || 0} active
              </p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Subdomains</CardTitle>
              <Search className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(program.total_subdomains || 0).toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">Discovered</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Scans</CardTitle>
              <Radar className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{program.total_scans || 0}</div>
              <p className="text-xs text-muted-foreground">
                {program.completed_scans || 0} completed
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Created</CardTitle>
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-lg font-bold">
                {new Date(program.created_at).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric'
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Data Access Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Subdomains */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5 text-blue-500" />
                Subdomains
              </CardTitle>
              <CardDescription>
                Discovered subdomains from Subfinder scans
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold mb-4">
                {(program.total_subdomains || 0).toLocaleString()}
              </div>
              <Button asChild className="w-full">
                <Link href={`/subdomains?asset=${program.id}`}>
                  <Search className="h-4 w-4 mr-2" />
                  View Subdomains
                </Link>
              </Button>
            </CardContent>
          </Card>

          {/* DNS Records */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5 text-green-500" />
                DNS Records
              </CardTitle>
              <CardDescription>
                A, AAAA, CNAME records from DNSx scans
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold mb-4 text-muted-foreground">
                View All
              </div>
              <Button asChild variant="outline" className="w-full">
                <Link href={`/dns?asset=${program.id}`}>
                  <Database className="h-4 w-4 mr-2" />
                  View DNS Records
                </Link>
              </Button>
            </CardContent>
          </Card>

          {/* HTTP Probes */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wifi className="h-5 w-5 text-orange-500" />
                HTTP Probes
              </CardTitle>
              <CardDescription>
                Live hosts and responses from HTTPx scans
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold mb-4 text-muted-foreground">
                View All
              </div>
              <Button asChild variant="outline" className="w-full">
                <Link href={`/probes?asset=${program.id}`}>
                  <Wifi className="h-4 w-4 mr-2" />
                  View HTTP Probes
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* API Access Info */}
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle className="text-lg">API Access</CardTitle>
            <CardDescription>
              Access this program&apos;s data programmatically via the API
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-muted/50 rounded-lg p-4 font-mono text-sm">
              <p className="text-muted-foreground mb-2"># Get subdomains for this program</p>
              <p>curl -H &quot;X-API-Key: YOUR_API_KEY&quot; \</p>
              <p className="ml-4">&quot;https://api.neobotnet.com/v1/programs/{program.id}/subdomains&quot;</p>
            </div>
            <Button asChild variant="link" className="mt-4 p-0">
              <Link href="/api-docs">
                View full API documentation →
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

