'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Globe, Server, Download, Calendar, ArrowRight, Loader2, Network } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { assetAPI, type AssetScanJob } from '@/lib/api/assets';
import { exportSubdomains, ExportFormat } from '@/lib/data-exports';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

export default function ReconPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  
  const [lastScan, setLastScan] = useState<AssetScanJob | null>(null);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [isExporting, setIsExporting] = useState(false);

  // Load last scan information
  useEffect(() => {
    const loadLastScan = async () => {
      if (!isAuthenticated) return;
      
      try {
        const scans = await assetAPI.listAssetScans(1);
        if (scans.length > 0) {
          setLastScan(scans[0]);
        }
      } catch (error) {
        // Silently fail - this is non-critical metadata
        // Not logging to avoid console noise for optional feature
      } finally {
        setIsLoadingData(false);
      }
    };

    if (isAuthenticated) {
      loadLastScan();
    }
  }, [isAuthenticated]);

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !authLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, authLoading, router]);

  // Export all subdomains as CSV
  const handleExportCSV = async () => {
    try {
      setIsExporting(true);
      
      // Fetch all subdomains (using high limit)
      const subdomains = await assetAPI.getAllUserSubdomains({ limit: 10000 });
      
      if (subdomains.length === 0) {
        toast.error('No subdomains to export');
        return;
      }

      // Transform to export format
      const exportData = subdomains.map(sub => ({
        subdomain: sub.subdomain,
        domain: sub.parent_domain,
        discovered_at: new Date(sub.discovered_at).toLocaleDateString(),
        scan_job_id: sub.scan_job_id
      }));

      await exportSubdomains(exportData, ExportFormat.CSV);
      toast.success(`Exported ${subdomains.length} subdomains to CSV`);
      
    } catch (error) {
      console.error('Failed to export subdomains:', error);
      toast.error('Failed to export subdomains');
    } finally {
      setIsExporting(false);
    }
  };

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
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header Section */}
        <div className="text-center space-y-3">
          <h1 className="text-4xl font-bold tracking-tight">
            Reconnaissance Data
          </h1>
          <p className="text-lg text-muted-foreground">
            Explore and analyze data collected from your reconnaissance operations
          </p>
        </div>

                        {/* Navigation Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
                  {/* Subdomains Card */}
                  <Card 
                    className="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-primary/50"
                    onClick={() => router.push('/subdomains')}
                  >
                    <CardHeader className="text-center pb-4">
                      <div className="flex justify-center mb-4">
                        <div className="rounded-full bg-blue-500/10 p-4">
                          <Globe className="h-8 w-8 text-blue-600 dark:text-blue-400" />
                        </div>
                      </div>
                      <CardTitle className="text-2xl">Subdomains</CardTitle>
                      <CardDescription className="text-base">
                        Explore discovered subdomains across your assets with advanced filtering
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button 
                        className="w-full" 
                        size="lg"
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push('/subdomains');
                        }}
                      >
                        View Subdomains
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                    </CardContent>
                  </Card>

                  {/* DNS Records Card */}
                  <Card 
                    className="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-primary/50"
                    onClick={() => router.push('/dns')}
                  >
                    <CardHeader className="text-center pb-4">
                      <div className="flex justify-center mb-4">
                        <div className="rounded-full bg-blue-500/10 p-4">
                          <Server className="h-8 w-8 text-blue-600 dark:text-blue-400" />
                        </div>
                      </div>
                      <CardTitle className="text-2xl">DNS Records</CardTitle>
                      <CardDescription className="text-base">
                        View DNS resolution results and analyze record types across your assets
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button 
                        className="w-full" 
                        size="lg"
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push('/dns');
                        }}
                      >
                        View DNS Records
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                    </CardContent>
                  </Card>

                  {/* HTTP Probes Card */}
                  <Card 
                    className="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-primary/50"
                    onClick={() => router.push('/probes')}
                  >
                    <CardHeader className="text-center pb-4">
                      <div className="flex justify-center mb-4">
                        <div className="rounded-full bg-green-500/10 p-4">
                          <Network className="h-8 w-8 text-green-600 dark:text-green-400" />
                        </div>
                      </div>
                      <CardTitle className="text-2xl">HTTP Probes</CardTitle>
                      <CardDescription className="text-base">
                        Analyze HTTP endpoints with status codes, technologies, and server details
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button 
                        className="w-full" 
                        size="lg"
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push('/probes');
                        }}
                      >
                        View HTTP Probes
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                    </CardContent>
                  </Card>
                </div>

        {/* Metadata Section */}
        <div className="border-t pt-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Last Scan Info */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Calendar className="h-4 w-4" />
              {isLoadingData ? (
                <span>Loading last scan info...</span>
              ) : lastScan ? (
                <span>
                  Last scan: <span className="font-medium text-foreground">{lastScan.asset_name}</span>
                  {' '}
                  {formatDistanceToNow(new Date(lastScan.created_at), { addSuffix: true })}
                </span>
              ) : (
                <span>No scans yet</span>
              )}
            </div>

            {/* Export CSV Button */}
            <Button
              variant="outline"
              onClick={handleExportCSV}
              disabled={isExporting}
            >
              {isExporting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Export All CSV
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
