'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { formatDistanceToNow } from 'date-fns';
import { Clock, CheckCircle, XCircle, AlertCircle, Loader2, Globe } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

import { assetAPI, type AssetScanJob } from '@/lib/api/assets';

interface ScanHistoryProps {
  refreshTrigger?: number; // To trigger refresh from parent
}

export default function ScanHistory({ refreshTrigger }: ScanHistoryProps) {
  const router = useRouter();
  const [scans, setScans] = useState<AssetScanJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadScans = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const scanJobs = await assetAPI.listAssetScans(20);
      setScans(scanJobs);
    } catch (err) {
      setError('Failed to load scan history');
      console.error('Error loading scans:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadScans();
  }, [refreshTrigger]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-400" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-400" />;
      case 'running':
        return <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-400" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="default" className="bg-green-600 hover:bg-green-700">Completed</Badge>;
      case 'failed':
        return <Badge variant="destructive" className="bg-red-600 hover:bg-red-700">Failed</Badge>;
      case 'running':
        return <Badge variant="secondary" className="bg-blue-600 hover:bg-blue-700 text-white">Running</Badge>;
      case 'pending':
        return <Badge variant="outline" className="border-yellow-500 text-yellow-400">Pending</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Scan History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="ml-2">Loading scan history...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Scan History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <XCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
            <p className="text-red-400">{error}</p>
            <Button onClick={loadScans} variant="outline" className="mt-4">
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Recent Asset Scans</CardTitle>
            <CardDescription>
              Your asset-level reconnaissance scan history
            </CardDescription>
          </div>
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => router.push('/subdomains')}
          >
            <Globe className="h-4 w-4 mr-2" />
            View All Subdomains
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {scans.length === 0 ? (
          <div className="text-center py-8">
            <Globe className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-muted-foreground">No asset scans yet</p>
            <p className="text-sm text-muted-foreground">Start your first asset scan from the Assets page!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {scans.map((scan) => (
              <div
                key={scan.id}
                className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center space-x-3">
                  {getStatusIcon(scan.status)}
                  <div>
                    <div className="font-medium">{scan.asset_name}</div>
                    <div className="text-sm text-muted-foreground">
                      {formatDistanceToNow(new Date(scan.created_at), { addSuffix: true })}
                      {scan.total_subdomains_found > 0 && (
                        <span className="ml-2">• {scan.total_subdomains_found} subdomains found</span>
                      )}
                      {scan.total_domains > 0 && (
                        <span className="ml-2">• {scan.total_domains} domains</span>
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  {getStatusBadge(scan.status)}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
