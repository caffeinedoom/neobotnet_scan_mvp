'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Search, 
  Building2,
  Activity,
  History,
  Zap,
  BarChart3,
  Loader2,
  Clock,
  ExternalLink,
  CheckCircle,
  AlertCircle,
  X  // Phase 2, Task 2.1
} from 'lucide-react';
import { cn } from '@/lib/utils';  // Phase 2, Task 2.1

// Import existing components
import ScanHistory from '@/components/recon/ScanHistory';

// Import unified reconnaissance data service and unified scans API
import { reconDataService, type ReconSummary, type ReconAsset } from '@/lib/api/recon-data';
import { scansAPI } from '@/lib/api/assets';
import type { UnifiedScanResponse } from '@/types/scans';
import { toast } from 'sonner';

// Hardcoded modules for optimal streaming (subfinder → dnsx → httpx)
// Note: Backend auto-includes dnsx when subfinder is present
const SCAN_MODULES = ['subfinder', 'httpx'];

// Scan tracking state for polling
interface ScanState {
  scanId: string | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | null;
  isPolling: boolean;
}

export default function ScansPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  
  // State management
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('asset'); // Start with asset tab since domain scan is removed
  
  // Stats state - using unified types
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

  // Assets state for asset scanning - using unified types
  const [assets, setAssets] = useState<ReconAsset[]>([]);
  
  // Asset selection state
  const [selectedAssets, setSelectedAssets] = useState<Set<string>>(new Set());
  
  // Scan state with polling
  const [scanState, setScanState] = useState<ScanState>({
    scanId: null,
    status: null,
    isPolling: false
  });
  const [isStartingScan, setIsStartingScan] = useState(false);

  // Enhanced scan tracking state (Phase 1, Task 1.1)
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [showScanCard, setShowScanCard] = useState(false);
  const [scanResults, setScanResults] = useState<{
    total_subdomains: number;
    assets_count: number;
  } | null>(null);

  // Load statistics and data using unified service
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      
      // UNIFIED DATA SERVICE: Single query replaces multiple API calls + client-side aggregation
      // Features: Smart caching, guaranteed data consistency, O(1) performance
      const { summary, assets } = await reconDataService.getScansData();
      
      setStats(summary);
      setAssets(assets);
      // Recent scans data is available via the unified service for ScanHistory component
      
    } catch (error) {
      console.error('Error loading scan data:', error);
    } finally {
      setLoading(false);
    }
  }, []); // Empty dependency array - this function doesn't depend on any state

  // Poll scan status every 3 seconds while scan is active
  useEffect(() => {
    let pollInterval: NodeJS.Timeout | null = null;

    const pollScanStatus = async () => {
      if (!scanState.scanId) return;

      try {
        const status = await scansAPI.getScanStatus(scanState.scanId);
        
        setScanState(prev => ({
          ...prev,
          status: status.status
        }));

        // If scan completed or failed, stop polling and refresh data
        if (status.status === 'completed' || status.status === 'failed') {
          if (pollInterval) {
            clearInterval(pollInterval);
          }
          
          // Store results for display in tracking card (Phase 1, Task 1.3)
          if (status.status === 'completed') {
            setScanResults({
              total_subdomains: status.results?.total_subdomains || 0,
              assets_count: status.asset_ids?.length || selectedAssets.size
            });
          }
          
          setScanState({
            scanId: null,
            status: null,
            isPolling: false
          });

          // Show completion toast
          if (status.status === 'completed') {
            toast.success('Scan completed!', {
              description: status.results 
                ? `Found ${status.results.total_subdomains} subdomains across ${status.asset_ids.length} asset(s)`
                : 'Scan finished successfully'
            });
          } else if (status.status === 'failed') {
            toast.error('Scan failed', {
              description: status.error_message || 'An error occurred during scanning'
            });
          }

          // Refresh data after completion
          setTimeout(() => {
            loadData();
          }, 2000);
        }
      } catch (error) {
        console.error('Error polling scan status:', error);
        // Stop polling on error
        if (pollInterval) {
          clearInterval(pollInterval);
        }
        setScanState({
          scanId: null,
          status: null,
          isPolling: false
        });
      }
    };

    // Start polling if scan is active
    if (scanState.scanId && scanState.isPolling) {
      pollInterval = setInterval(pollScanStatus, 3000); // Poll every 3 seconds
      // Immediate first poll
      pollScanStatus();
    }

    // Cleanup on unmount or when polling stops
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [scanState.scanId, scanState.isPolling, loadData]);

  // Timer effect for elapsed time tracking (Phase 1, Task 1.2)
  useEffect(() => {
    if (scanState.isPolling && showScanCard) {
      const timer = setInterval(() => {
        setElapsedSeconds(prev => prev + 1);
      }, 1000);
      
      return () => clearInterval(timer);
    }
  }, [scanState.isPolling, showScanCard]);

  // Restore scan tracking on page load (Phase 3.5, Task 3.5.2)
  useEffect(() => {
    const restoreRunningScan = async () => {
      // Skip if already tracking a scan
      if (scanState.scanId || !isAuthenticated) {
        return;
      }

      try {
        // Query backend for running scans (most recent first)
        const response = await scansAPI.listScans({ 
          status: 'running', 
          limit: 1 
        });

        if (response.scans && response.scans.length > 0) {
          const runningScan = response.scans[0];
          
          // Calculate elapsed time from created_at (approximation)
          // Note: Using created_at as started_at not available in ScanSummary
          const createdAt = new Date(runningScan.created_at);
          const elapsed = Math.floor((Date.now() - createdAt.getTime()) / 1000);
          
          // Restore tracking state
          setShowScanCard(true);
          setElapsedSeconds(Math.max(0, elapsed)); // Ensure non-negative
          setScanState({
            scanId: runningScan.scan_id,
            status: runningScan.status,
            isPolling: true
          });

          // Log restoration for debugging
          console.log(`[Scan Tracking] Restored running scan: ${runningScan.scan_id} (elapsed: ${elapsed}s)`);
        }
      } catch (error) {
        // Silently fail - restore is best-effort, not critical
        console.error('[Scan Tracking] Failed to restore running scan:', error);
      }
    };

    // Run once on mount when authenticated
    if (isAuthenticated && !isLoading) {
      restoreRunningScan();
    }
  }, [isAuthenticated, isLoading]); // Only run when auth state settles

  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      // Only redirect if we're not already on an auth page to prevent infinite loops
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Handle asset selection for batch processing
  const handleAssetSelection = (assetId: string, checked: boolean) => {
    setSelectedAssets(prev => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(assetId);
      } else {
        newSet.delete(assetId);
      }
      return newSet;
    });
  };

  // Handle select all toggle
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedAssets(new Set(assets.map(asset => asset.id)));
    } else {
      setSelectedAssets(new Set());
    }
  };

  // No module selection needed - hardcoded to optimal 'subfinder + dnsx + httpx'
  // Backend auto-includes dnsx for data persistence when subfinder is present

  // Helper functions for scan tracking (Phase 1, Task 1.4)
  
  // Format elapsed seconds to MM:SS
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle manual card dismissal
  const handleCloseScanCard = () => {
    setShowScanCard(false);
    setElapsedSeconds(0);
    setScanResults(null);
    setScanState({
      scanId: null,
      status: null,
      isPolling: false
    });
  };

  // Start unified scan
  const handleStartScan = async () => {
    if (selectedAssets.size === 0) {
      toast.error('No assets selected', {
        description: 'Please select at least one asset to scan'
      });
      return;
    }

    // Immediate visual feedback
    setIsStartingScan(true);

    // Initialize scan tracking card (Phase 1, Task 1.5)
    setShowScanCard(true);
    setElapsedSeconds(0);
    setScanResults(null);

    try {
      // Build request body - map each asset to scan configuration
      const assetConfigs: Record<string, { modules: string[]; active_domains_only: boolean }> = {};
      selectedAssets.forEach(assetId => {
        assetConfigs[assetId] = {
          modules: SCAN_MODULES,
          active_domains_only: true
        };
      });

      // Start unified scan with selected assets
      const response: UnifiedScanResponse = await scansAPI.startScan({
        assets: assetConfigs
      });

      // Start polling for scan status
      setScanState({
        scanId: response.scan_id,
        status: response.status,
        isPolling: true
      });

      // Success toast
      toast.success('Scan started!', {
        description: `Running subfinder → dnsx → httpx on ${selectedAssets.size} asset${selectedAssets.size > 1 ? 's' : ''} (${totalSelectedDomains} domain${totalSelectedDomains !== 1 ? 's' : ''}). Streaming results in real-time.`
      });

      // Clear selection after starting scan
      setSelectedAssets(new Set());

      // Invalidate cache and trigger refresh to show new scan
      reconDataService.invalidateCache();
      setRefreshTrigger(prev => prev + 1);
      setTimeout(() => loadData(), 1000);

    } catch (error) {
      console.error('Failed to start scan:', error);
      // Hide scan card on error (Phase 1, Task 1.5)
      setShowScanCard(false);
      toast.error('Failed to start scan', {
        description: error instanceof Error ? error.message : 'Please try again or contact support if the issue persists'
      });
    } finally {
      setIsStartingScan(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated, refreshTrigger, loadData]);

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  const selectedAssetsData = assets.filter(asset => selectedAssets.has(asset.id));
  const totalSelectedDomains = selectedAssetsData.reduce((sum, asset) => sum + (asset.apex_domain_count || 0), 0);

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Reconnaissance Scans
            </h1>
            <p className="text-muted-foreground mt-2">
              Manage and monitor your subdomain enumeration and asset scanning operations.
            </p>
          </div>
          

        </div>

        {/* Statistics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Scans</CardTitle>
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.total_scans}</div>
              <p className="text-xs text-muted-foreground">All time</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Completed</CardTitle>
              <Activity className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.completed_scans}</div>
              <p className="text-xs text-muted-foreground">Successful scans</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Running</CardTitle>
              <Zap className="h-4 w-4 text-yellow-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.pending_scans}</div>
              <p className="text-xs text-muted-foreground">In progress</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Failed</CardTitle>
              <Activity className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.failed_scans}</div>
              <p className="text-xs text-muted-foreground">Errors</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Subdomains</CardTitle>
              <Search className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.total_subdomains}</div>
              <p className="text-xs text-muted-foreground">Discovered</p>
            </CardContent>
          </Card>
        </div>

        {/* Enhanced Scan Tracking Card - Phase 2, Task 2.2 */}
        {showScanCard && (
          <Card 
            className={cn(
              "transition-all duration-500 ease-in-out",
              scanState.isPolling
                ? "border-blue-500/30 bg-blue-500/5 dark:border-blue-400/30 dark:bg-blue-400/5 animate-pulse-border"
                : "border-green-500/30 bg-green-500/5 dark:border-green-400/30 dark:bg-green-400/5"
            )}
          >
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center justify-between">
                {/* Left: Icon + Status */}
                <div className="flex items-center gap-3">
                  {scanState.isPolling ? (
                    <Loader2 className="h-6 w-6 text-blue-600 dark:text-blue-400 animate-spin" />
                  ) : (
                    <CheckCircle className="h-6 w-6 text-green-600 dark:text-green-400" />
                  )}
                  
                  <div>
                    <p className="text-base font-semibold">
                      {scanState.isPolling 
                        ? `🔄 Scanning ${selectedAssets.size || scanResults?.assets_count || 0} asset${(selectedAssets.size || scanResults?.assets_count || 0) > 1 ? 's' : ''}...`
                        : "✅ Scan complete!"
                      }
                    </p>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      {scanState.isPolling
                        ? "▸ Streaming: subfinder → dnsx → httpx"
                        : `Found ${scanResults?.total_subdomains || 0} subdomains across ${scanResults?.assets_count || 0} asset${(scanResults?.assets_count || 0) > 1 ? 's' : ''}`
                      }
                    </p>
                  </div>
                </div>
                
                {/* Right: Timer + Close Button */}
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="text-sm">
                    ⏱️ {formatTime(elapsedSeconds)}
                  </Badge>
                  
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCloseScanCard}
                    className="h-8 w-8 p-0 hover:bg-slate-100 dark:hover:bg-slate-800"
                    aria-label="Close scan status"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Scanning Interface - Organized with Tabs (Domain Scan Removed) */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="asset" className="flex items-center space-x-2">
              <Building2 className="h-4 w-4" />
              <span>Asset Scan</span>
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center space-x-2">
              <History className="h-4 w-4" />
              <span>Scan History</span>
            </TabsTrigger>
          </TabsList>

          {/* Enhanced Asset-Based Scanning with Integrated Selection Controls */}
          <TabsContent value="asset" className="space-y-4">
            {/* Module Selection Card */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">Scan Configuration</CardTitle>
                    <CardDescription>
                      Optimized streaming scan using Subfinder, DNSx, and HTTPx
                    </CardDescription>
                  </div>
                  <Badge variant="outline" className="text-blue-600 dark:text-blue-400">
                    Streaming Scan
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {/* Fixed Module Configuration Info */}
                  <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Zap className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                        Real-time Streaming Scan
                      </span>
                    </div>
                    <p className="text-sm text-blue-700 dark:text-blue-300 mb-3">
                      Subfinder discovers subdomains and streams them to DNSx for DNS resolution, then HTTPx probes web services. 
                      This parallel pipeline provides the fastest results and optimal resource utilization.
                    </p>
                    <div className="flex items-center gap-2 text-sm text-blue-800 dark:text-blue-200">
                      <Activity className="h-4 w-4" />
                      <span className="font-mono">subfinder → dnsx → httpx</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Building2 className="h-5 w-5 text-purple-500" />
                  <span>Asset-Based Scanning</span>
                </CardTitle>
                <CardDescription>
                  Scan all apex domains within an asset for comprehensive reconnaissance across your bug bounty targets.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Integrated Control Panel */}
                  {assets.length > 0 && (
                    <div className="flex items-center justify-between p-4 bg-slate-50/50 dark:bg-slate-900/50 rounded-lg border border-slate-200 dark:border-slate-700">
                      {/* Left: Selection Controls */}
                      <div className="flex items-center gap-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (selectedAssets.size === assets.length) {
                              setSelectedAssets(new Set());
                            } else {
                              handleSelectAll(true);
                            }
                          }}
                          className="font-bold text-slate-700 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-300 dark:hover:text-slate-100 dark:hover:bg-slate-800"
                        >
                          {selectedAssets.size === assets.length ? 'UNSELECT ALL' : 'SELECT ALL'}
                        </Button>
                        {selectedAssets.size > 0 && (
                          <div className="h-4 w-px bg-slate-300 dark:bg-slate-600" />
                        )}
                      </div>

                      {/* Middle: Stats and Actions */}
                      <div className="flex items-center gap-6">
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span className="flex items-baseline gap-2">
                            <span className="text-lg font-semibold text-foreground">
                              {assets.length}
                            </span>
                            <span>assets</span>
                          </span>
                                                     <span className="flex items-baseline gap-2">
                             <span className="text-lg font-semibold text-foreground">
                               {selectedAssets.size > 0 ? totalSelectedDomains : assets.reduce((total, asset) => total + (asset.apex_domain_count || 0), 0)}
                             </span>
                             <span>domains</span>
                           </span>
                          {selectedAssets.size > 0 && (
                            <span className="flex items-baseline gap-2 text-slate-600 dark:text-slate-400">
                              <span className="text-lg font-semibold">
                                {selectedAssets.size}
                              </span>
                              <span>selected</span>
                            </span>
                          )}
                        </div>

                        {/* Right: Action Button */}
                        <Button
                          size="sm"
                          onClick={selectedAssets.size > 0 ? handleStartScan : undefined}
                          disabled={selectedAssets.size === 0 || isStartingScan || scanState.isPolling}
                          className="bg-slate-900 hover:bg-slate-800 text-white dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
                        >
                          {isStartingScan || scanState.isPolling ? (
                            <>
                              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                              {isStartingScan ? 'Starting...' : 'Scanning...'}
                            </>
                          ) : (
                            <>
                              <Zap className="h-4 w-4 mr-2" />
                              Start Scan {selectedAssets.size > 0 ? `(${selectedAssets.size})` : ''}
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  )}



                  {loading ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {[...Array(3)].map((_, i) => (
                        <Card key={i} className="border-dashed">
                          <CardContent className="p-4">
                            <div className="h-6 bg-muted animate-pulse rounded w-3/4 mb-2" />
                            <div className="h-4 bg-muted animate-pulse rounded w-1/2" />
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  ) : assets.length === 0 ? (
                    <Card className="border-dashed">
                      <CardContent className="flex flex-col items-center justify-center py-8">
                        <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
                        <h3 className="text-lg font-medium mb-2">No assets available</h3>
                        <p className="text-muted-foreground text-center mb-4">
                          Create assets first to enable asset-based scanning.
                        </p>
                        <Button onClick={() => router.push('/assets/create')}>
                          Create Your First Asset
                        </Button>
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {assets.map((asset) => (
                        <Card 
                          key={asset.id} 
                          className={`transition-all duration-200 ${
                            selectedAssets.has(asset.id) 
                              ? 'ring-2 ring-slate-400 bg-slate-100/50 border-slate-400/50 shadow-lg shadow-slate-400/10 dark:ring-slate-500 dark:bg-slate-800/50 dark:border-slate-500/50 dark:shadow-slate-500/10' 
                              : 'hover:shadow-md hover:border-primary/20'
                          }`}
                        >
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between mb-3">
                              <div className="flex items-center gap-3">
                                <Checkbox
                                  checked={selectedAssets.has(asset.id)}
                                  onCheckedChange={(checked) => handleAssetSelection(asset.id, checked as boolean)}
                                  aria-label={`Select ${asset.name}`}
                                />
                                <div className="flex-1">
                                  <h3 className="font-semibold truncate" title={asset.name}>
                                    {asset.name}
                                  </h3>
                                  <p className="text-sm text-muted-foreground">
                                    {asset.apex_domain_count || 0} domains
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-xs">
                                  {asset.total_subdomains || 0} subs
                                </Badge>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => window.open(`/assets/${asset.id}`, '_blank')}
                                  className="text-muted-foreground hover:text-foreground"
                                >
                                  <ExternalLink className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                            
                            {/* Asset Status Information */}
                            <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-muted/30">
                              <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {asset.last_scan_date ? (
                                  <>Last scan: {new Date(asset.last_scan_date).toLocaleDateString()}</>
                                ) : (
                                  <>Never scanned</>
                                )}
                              </span>
                              <span className="flex items-center gap-1">
                                {(asset.apex_domain_count || 0) > 0 ? (
                                  <>
                                    <CheckCircle className="h-3 w-3 text-green-500" />
                                    Ready
                                  </>
                                ) : (
                                  <>
                                    <AlertCircle className="h-3 w-3 text-amber-500" />
                                    No domains
                                  </>
                                )}
                              </span>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Scan History */}
          <TabsContent value="history" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <History className="h-5 w-5 text-green-500" />
                  <span>Scan History & Monitoring</span>
                </CardTitle>
                <CardDescription>
                  Monitor your recent scans and view detailed results from all reconnaissance operations.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScanHistory key={refreshTrigger} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
