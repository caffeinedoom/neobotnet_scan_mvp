'use client';

import { useState, useEffect, useCallback } from 'react';
import { Copy, ExternalLink, CheckCircle, Globe, Loader2, XCircle, Shield, Cloud, Eye, Calendar, Server, Activity } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

import { reconAPI } from '@/lib/api';
import { ScanJobWithResults, EnhancedSubdomain, ScanProgress } from '@/types/recon';

interface ScanResultsProps {
  jobId: string;
  onClose?: () => void;
}

interface SubdomainCardProps {
  subdomain: EnhancedSubdomain;
}

function SubdomainCard({ subdomain }: SubdomainCardProps) {
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard!');
    } catch {
      toast.error('Failed to copy to clipboard');
    }
  };

  /**
   * Get icon for module badge.
   * 
   * CLEANUP NOTE (2025-10-06): Removed cloud_ssl, kept future modules commented for reference.
   */
  const getModuleIcon = (module: string) => {
    switch (module.toLowerCase()) {
      case 'subfinder': return Globe;
      // Future modules (uncomment when implemented):
      // case 'dns_bruteforce': return Activity;
      // case 'http_probe': return Server;
      default: return Eye;
    }
  };

  /**
   * Get color for module badge.
   * 
   * CLEANUP NOTE (2025-10-06): Removed cloud_ssl, kept future modules commented for reference.
   */
  const getModuleColor = (module: string) => {
    switch (module.toLowerCase()) {
      case 'subfinder': return 'bg-blue-600';
      // Future modules (uncomment when implemented):
      // case 'dns_bruteforce': return 'bg-slate-600';
      // case 'http_probe': return 'bg-purple-600';
      default: return 'bg-gray-600';
    }
  };

  const isSSLValid = () => {
    if (!subdomain.ssl_valid_until) return null;
    return new Date(subdomain.ssl_valid_until) > new Date();
  };

  const getDaysUntilExpiry = () => {
    if (!subdomain.ssl_valid_until) return null;
    const now = new Date();
    const expiry = new Date(subdomain.ssl_valid_until);
    const diffTime = expiry.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const ModuleIcon = getModuleIcon(subdomain.source_module);
  const moduleColor = getModuleColor(subdomain.source_module);
  const sslValid = isSSLValid();
  const daysUntilExpiry = getDaysUntilExpiry();

  return (
    <div className="border rounded-lg p-4 hover:bg-muted/50 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* Main subdomain with source module */}
          <div className="flex items-center space-x-3 mb-3">
            <div className={`p-1.5 rounded-lg ${moduleColor}`}>
              <ModuleIcon className="h-3 w-3 text-white" />
            </div>
            <div className="font-mono text-sm font-medium">{subdomain.subdomain}</div>
            <Badge variant="outline" className="text-xs">
              {subdomain.source_module}
            </Badge>
            {subdomain.cloud_provider && (
              <Badge variant="secondary" className="text-xs">
                <Cloud className="h-3 w-3 mr-1" />
                {subdomain.cloud_provider}
              </Badge>
            )}
          </div>

          {/* SSL Certificate Information */}
          {subdomain.ssl_subject_cn && (
            <div className="mb-3 p-3 bg-muted/30 rounded-lg">
              <div className="flex items-center space-x-2 mb-2">
                <Shield className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium">SSL Certificate</span>
                {sslValid !== null && (
                  <Badge 
                    variant={sslValid ? "default" : "destructive"}
                    className="text-xs"
                  >
                    {sslValid ? "Valid" : "Expired"}
                  </Badge>
                )}
                {subdomain.ssl_is_wildcard && (
                  <Badge variant="outline" className="text-xs">Wildcard</Badge>
                )}
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div>
                  <span className="font-medium">Subject:</span> {subdomain.ssl_subject_cn}
                </div>
                {subdomain.ssl_issuer && (
                  <div>
                    <span className="font-medium">Issuer:</span> {subdomain.ssl_issuer}
                  </div>
                )}
                {subdomain.ssl_valid_from && (
                  <div>
                    <span className="font-medium">Valid From:</span> {new Date(subdomain.ssl_valid_from).toLocaleDateString()}
                  </div>
                )}
                {subdomain.ssl_valid_until && (
                  <div>
                    <span className="font-medium">Valid Until:</span> {new Date(subdomain.ssl_valid_until).toLocaleDateString()}
                    {daysUntilExpiry !== null && (
                      <span className={`ml-1 ${daysUntilExpiry < 30 ? 'text-amber-600' : daysUntilExpiry < 7 ? 'text-red-500' : ''}`}>
                        ({daysUntilExpiry} days)
                      </span>
                    )}
                  </div>
                )}
                {subdomain.ssl_serial_number && (
                  <div className="md:col-span-2">
                    <span className="font-medium">Serial:</span> {subdomain.ssl_serial_number}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Technical Details */}
          <div className="flex items-center space-x-4 text-xs text-muted-foreground">
            <div className="flex items-center space-x-1">
              <Calendar className="h-3 w-3" />
              <span>Discovered {new Date(subdomain.discovered_at).toLocaleDateString()}</span>
            </div>
            
            {subdomain.ip_addresses && subdomain.ip_addresses.length > 0 && (
              <div className="flex items-center space-x-1">
                <Server className="h-3 w-3" />
                <span>{subdomain.ip_addresses.join(', ')}</span>
              </div>
            )}
            
            {subdomain.status_code && (
              <div className="flex items-center space-x-1">
                <Activity className="h-3 w-3" />
                <span>HTTP {subdomain.status_code}</span>
              </div>
            )}

            {subdomain.discovery_method && (
              <div className="flex items-center space-x-1">
                <Eye className="h-3 w-3" />
                <span>{subdomain.discovery_method}</span>
              </div>
            )}
          </div>

          {/* Source Range for Cloud SSL */}
          {subdomain.source_ip_range && (
            <div className="mt-2 text-xs text-muted-foreground">
              <span className="font-medium">Source Range:</span> {subdomain.source_ip_range}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2 ml-4">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => copyToClipboard(subdomain.subdomain)}
            title="Copy subdomain"
          >
            <Copy className="h-3 w-3" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => window.open(`https://${subdomain.subdomain}`, '_blank')}
            title="Open in browser"
          >
            <ExternalLink className="h-3 w-3" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function ScanResults({ jobId, onClose }: ScanResultsProps) {
  const [scanData, setScanData] = useState<ScanJobWithResults | null>(null);
  const [enhancedSubdomains, setEnhancedSubdomains] = useState<EnhancedSubdomain[]>([]);
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  const loadScanResults = useCallback(async () => {
    try {
      setError(null);
      
      // Load basic scan data
      const data = await reconAPI.getScanJob(jobId);
      setScanData(data);
      
      // Try to load enhanced subdomains if available
              try {
          const enhanced = await reconAPI.getEnhancedSubdomains(jobId);
          setEnhancedSubdomains(enhanced);
        } catch {
          console.warn('Enhanced subdomains not available, using basic data');
        // Convert basic subdomains to enhanced format
        if (Array.isArray(data.subdomains) && typeof data.subdomains[0] === 'string') {
          const basicEnhanced = (data.subdomains as string[]).map((subdomain, index) => ({
            id: `${jobId}-${index}`,
            subdomain,
            scan_job_id: jobId,
            source_module: 'subfinder',
            discovered_at: data.created_at,
          })) as EnhancedSubdomain[];
          setEnhancedSubdomains(basicEnhanced);
        }
      }
      
      // Load progress for running scans
              if (data.status === 'running' || data.status === 'pending') {
          try {
            const progressData = await reconAPI.getScanProgress(jobId);
            setProgress(progressData);
          } catch {
            console.warn('Progress data not available');
        }
      }
      
    } catch (error) {
      setError('Failed to load scan results');
      console.error('Error loading scan results:', error);
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    loadScanResults();
  }, [loadScanResults]);

  // Set up auto-refresh for running scans
  useEffect(() => {
    if (scanData?.status === 'running' || scanData?.status === 'pending') {
      const interval = setInterval(() => {
        loadScanResults();
      }, 5000); // Refresh every 5 seconds
      setRefreshInterval(interval);
      
      return () => {
        if (interval) clearInterval(interval);
      };
    } else {
      if (refreshInterval) {
        clearInterval(refreshInterval);
        setRefreshInterval(null);
      }
    }
  }, [scanData?.status, loadScanResults, refreshInterval]);

  const copyAllSubdomains = () => {
    if (enhancedSubdomains.length > 0) {
      const subdomainList = enhancedSubdomains.map(sub => sub.subdomain).join('\n');
      navigator.clipboard.writeText(subdomainList);
      toast.success('All subdomains copied to clipboard!');
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Scan Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="ml-2">Loading scan results...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !scanData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Scan Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <XCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
            <p className="text-red-400">{error || 'No data available'}</p>
            <div className="flex justify-center space-x-2 mt-4">
              <Button onClick={loadScanResults} variant="outline">
                Try Again
              </Button>
              {onClose && (
                <Button onClick={onClose} variant="ghost">
                  Back
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-600 hover:bg-green-700"><CheckCircle className="h-3 w-3 mr-1" />Completed</Badge>;
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

  const modules = scanData.modules || ['subfinder'];
  const moduleStats = enhancedSubdomains.reduce((acc, sub) => {
    acc[sub.source_module] = (acc[sub.source_module] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center space-x-2">
              <Globe className="h-5 w-5" />
              <span>{scanData.domain}</span>
              {getStatusBadge(scanData.status)}
            </CardTitle>
            <CardDescription>
              Scan completed on {new Date(scanData.created_at).toLocaleDateString()} • 
              {enhancedSubdomains.length} subdomains found
              {modules.length > 1 && ` using ${modules.length} modules`}
            </CardDescription>
            
            {/* Module Statistics */}
            {Object.keys(moduleStats).length > 1 && (
              <div className="flex items-center space-x-2 mt-2">
                {Object.entries(moduleStats).map(([module, count]) => (
                  <Badge key={module} variant="outline" className="text-xs">
                    {module}: {count}
                  </Badge>
                ))}
              </div>
            )}
          </div>
          <div className="flex space-x-2">
            {enhancedSubdomains.length > 0 && (
              <Button onClick={copyAllSubdomains} variant="outline" size="sm">
                <Copy className="h-4 w-4 mr-1" />
                Copy All
              </Button>
            )}
            {onClose && (
              <Button onClick={onClose} variant="ghost" size="sm">
                Back
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Progress Information for Running Scans */}
        {progress && (scanData.status === 'running' || scanData.status === 'pending') && (
          <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-blue-900 dark:text-blue-100">Scan Progress</h3>
              <Badge variant="secondary" className="bg-blue-100 text-blue-800">
                {progress.progress.current_phase}
              </Badge>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-blue-600 dark:text-blue-400 font-medium">Progress:</span>
                <div>{progress.progress.progress_percent.toFixed(1)}%</div>
              </div>
              <div>
                <span className="text-blue-600 dark:text-blue-400 font-medium">Results:</span>
                <div>{progress.progress.total_results}</div>
              </div>
              <div>
                <span className="text-blue-600 dark:text-blue-400 font-medium">DB Writes:</span>
                <div>{progress.progress.database_writes} ({progress.progress.db_success_rate.toFixed(1)}%)</div>
              </div>
              <div>
                <span className="text-blue-600 dark:text-blue-400 font-medium">Memory:</span>
                <div>{progress.progress.memory_usage_mb}MB</div>
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {scanData.status === 'failed' && scanData.error_message && (
          <div className="mb-4 p-3 bg-red-900/20 border border-red-600/50 rounded-lg">
            <p className="text-red-300 text-sm">{scanData.error_message}</p>
          </div>
        )}

        {/* Subdomains List */}
        {enhancedSubdomains.length > 0 ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">
                Discovered Subdomains ({enhancedSubdomains.length})
              </h3>
            </div>
            
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {enhancedSubdomains.map((subdomain, index) => (
                <SubdomainCard key={subdomain.id || `${subdomain.scan_job_id}-${index}`} subdomain={subdomain} />
              ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <Globe className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-muted-foreground">No subdomains found</p>
            <p className="text-sm text-muted-foreground">
              {scanData.status === 'completed' 
                ? 'This domain may not have any discoverable subdomains.'
                : 'Scan may still be in progress or failed.'}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
