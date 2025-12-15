'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  Building2, 
  Plus, 
  Globe, 
  Search, 
  Activity, 
  Eye,
  Upload,
  Trash2
} from 'lucide-react';
import Link from 'next/link';
import { assetAPI } from '@/lib/api/assets';
import { reconDataService, type ReconAsset, type ReconSummary } from '@/lib/api/recon-data';
import { toast } from 'sonner';
import { ConfirmDeleteDialog } from '@/components/ui/confirm-delete-dialog';
import { DomainUploadModal } from '@/components/ui/domain-upload-modal';

export default function AssetsPage() {
  const router = useRouter();
  const pathname = usePathname(); // Track current route for navigation detection
  const { isAuthenticated, isLoading } = useAuth();
  
  // State management - using unified types
  const [assets, setAssets] = useState<ReconAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingAssetId, setDeletingAssetId] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [assetToDelete, setAssetToDelete] = useState<ReconAsset | null>(null);
  
  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadAsset, setUploadAsset] = useState<ReconAsset | null>(null);
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

  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      // Only redirect if we're not already on an auth page to prevent infinite loops
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Load assets and stats using unified service
  const loadAssets = async () => {
    try {
      setLoading(true);
      
      // UNIFIED DATA SERVICE: Single query replaces multiple API calls
      // Features: Eliminates N+1 queries, guarantees data consistency
      const { assets, summary } = await reconDataService.getAssetsData();
      
      setAssets(assets);
      setStats(summary);
      
    } catch (error) {
      console.error('Failed to load assets:', error);
      toast.error('Failed to load assets');
      
      // Show empty state on error
      setAssets([]);
      setStats({
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
    } finally {
      setLoading(false);
    }
  };

  // Handle opening the delete confirmation dialog
  const handleDeleteAsset = async (assetId: string) => {
    const asset = assets.find(a => a.id === assetId);
    if (asset) {
      setAssetToDelete(asset);
      setShowDeleteDialog(true);
    }
  };

  // Handle opening the upload modal
  const handleUploadDomains = (assetId: string) => {
    const asset = assets.find(a => a.id === assetId);
    if (asset) {
      setUploadAsset(asset);
      setShowUploadModal(true);
    }
  };

  // Handle successful upload - refresh asset list
  const handleUploadSuccess = async () => {
    // Invalidate cache to ensure fresh data
    reconDataService.invalidateCache();
    
    // Small delay to ensure backend has fully processed the upload
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Refresh the entire asset list to show updated counts
    await loadAssets();
  };

  // Handle closing upload modal
  const handleCloseUploadModal = () => {
    setShowUploadModal(false);
    setUploadAsset(null);
  };

  // Scan functionality moved to /scans page for unified experience

  // Handle confirmed deletion
  const handleConfirmDelete = async () => {
    if (!assetToDelete) return;
    
    try {
      setDeletingAssetId(assetToDelete.id);
      await assetAPI.deleteAsset(assetToDelete.id);
      
      // Remove asset from local state
      setAssets(prev => prev.filter(asset => asset.id !== assetToDelete.id));
      
      // Invalidate cache to ensure fresh data on next load
      reconDataService.invalidateCache();
      
      // Update stats optimistically
      setStats(prev => ({
        ...prev,
        total_assets: prev.total_assets - 1,
        active_assets: prev.active_assets - 1,
        total_domains: prev.total_domains - (assetToDelete.apex_domain_count || 0),
        total_subdomains: prev.total_subdomains - (assetToDelete.total_subdomains || 0)
      }));
      
      toast.success(`Asset "${assetToDelete.name}" deleted successfully`);
      
    } catch (error) {
      console.error('Failed to delete asset:', error);
      toast.error(`Failed to delete asset "${assetToDelete.name}"`);
    } finally {
      setDeletingAssetId(null);
      setShowDeleteDialog(false);
      setAssetToDelete(null);
    }
  };

  // Handle closing the dialog
  const handleCloseDeleteDialog = () => {
    setShowDeleteDialog(false);
    setAssetToDelete(null);
  };

  // Load assets on initial mount and when auth changes
  useEffect(() => {
    if (isAuthenticated) {
      loadAssets();
    }
  }, [isAuthenticated]);

  // Detect Next.js router navigation back to /assets and reload data
  useEffect(() => {
    // Only reload if authenticated and we're on the assets page
    if (isAuthenticated && pathname === '/assets') {
      reconDataService.invalidateCache();
      loadAssets();
    }
  }, [pathname, isAuthenticated]); // Re-run when pathname or auth changes

  // Reload assets when page becomes visible (tab switching, browser navigation)
  useEffect(() => {
    if (!isAuthenticated) return;

    // Reload when page visibility changes (tab switching)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        reconDataService.invalidateCache();
        loadAssets();
      }
    };

    // Reload when window regains focus (browser back button, navigation)
    const handleFocus = () => {
      reconDataService.invalidateCache();
      loadAssets();
    };

    // Add event listeners
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);

    // Cleanup listeners on unmount
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, [isAuthenticated]); // Re-setup listeners if auth changes

  if (!isAuthenticated && !isLoading) {
    return null; // Will redirect
  }

  // Removed loading spinner - we'll show skeleton content instead
  // This prevents flickering by maintaining consistent layout

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Asset Management
            </h1>
            <p className="text-muted-foreground mt-2">
              Manage your bug bounty targets and reconnaissance assets.
            </p>
          </div>
          <Button asChild>
            <Link href="/assets/create" className="flex items-center space-x-2">
              <Plus className="h-4 w-4" />
              <span>Add Asset</span>
            </Link>
          </Button>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Total Assets
              </CardTitle>
              <Building2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12 mb-2" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_assets}</div>
              )}
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-3 bg-muted animate-pulse rounded w-16" />
              ) : (
                <p className="text-xs text-muted-foreground">
                  {stats.active_assets} active
                </p>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Domains
              </CardTitle>
              <Globe className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12 mb-2" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_domains}</div>
              )}
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-3 bg-muted animate-pulse rounded w-20" />
              ) : (
                <p className="text-xs text-muted-foreground">
                  Apex domains tracked
                </p>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Subdomains
              </CardTitle>
              <Search className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12 mb-2" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_subdomains}</div>
              )}
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-3 bg-muted animate-pulse rounded w-18" />
              ) : (
                <p className="text-xs text-muted-foreground">
                  Total discovered
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Active
              </CardTitle>
              <Activity className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12 mb-2" />
              ) : (
                <div className="text-2xl font-bold">{stats.active_assets}</div>
              )}
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-3 bg-muted animate-pulse rounded w-20" />
              ) : (
                <p className="text-xs text-muted-foreground">
                  Assets monitoring
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Assets Grid - Simplified Design with Enhanced Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {loading || isLoading || !isAuthenticated ? (
            // Skeleton placeholders while loading - maintains layout to prevent flickering
            [...Array(6)].map((_, i) => (
              <Card key={`skeleton-${i}`} className="border">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <div className="h-6 bg-muted animate-pulse rounded w-3/4" />
                    </div>
                    <div className="flex space-x-1">
                      <div className="h-8 w-8 bg-muted animate-pulse rounded" />
                      <div className="h-8 w-8 bg-muted animate-pulse rounded" />
                      <div className="h-8 w-8 bg-muted animate-pulse rounded" />
                      <div className="h-8 w-8 bg-muted animate-pulse rounded" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="h-8 bg-muted animate-pulse rounded w-12 mb-1" />
                      <div className="h-3 bg-muted animate-pulse rounded w-20" />
                    </div>
                    <div>
                      <div className="h-8 bg-muted animate-pulse rounded w-12 mb-1" />
                      <div className="h-3 bg-muted animate-pulse rounded w-16" />
                    </div>
                  </div>
                  <div className="h-4 bg-muted animate-pulse rounded w-32" />
                </CardContent>
              </Card>
            ))
          ) : (
            // Actual asset cards
            assets.map((asset) => (
              <Card key={asset.id} className="hover:shadow-lg transition-all duration-200 border hover:border-primary/20">
                <CardContent className="p-6">
                  {/* Asset Name and Action Buttons */}
                  <div className="flex items-start justify-between mb-4 gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold truncate" title={asset.name}>
                        {asset.name}
                      </h3>

                    </div>
                    
                    {/* Action buttons - View, Upload, Delete */}
                    <div className="flex space-x-1 flex-shrink-0">
                      <Button 
                        variant="ghost" 
                        size="sm"
                        className="h-8 w-8 p-0 hover:bg-blue-50 hover:text-blue-600"
                        title="View asset details"
                        asChild
                      >
                        <Link href={`/assets/${asset.id}`}>
                          <Eye className="h-4 w-4" />
                        </Link>
                      </Button>
                      
                      <Button 
                        variant="ghost" 
                        size="sm"
                        className="h-8 w-8 p-0 hover:bg-green-50 hover:text-green-600"
                        title="Upload domains"
                        onClick={() => handleUploadDomains(asset.id)}
                      >
                        <Upload className="h-4 w-4" />
                      </Button>
                      
                      <Button 
                        variant="ghost" 
                        size="sm"
                        className="h-8 w-8 p-0 hover:bg-red-50 hover:text-red-600"
                        title="Delete asset"
                        onClick={() => handleDeleteAsset(asset.id)}
                        disabled={deletingAssetId === asset.id}
                      >
                        {deletingAssetId === asset.id ? (
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-red-600 border-t-transparent" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* Domain and Subdomain Counts */}
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="text-2xl font-bold text-white">{asset.apex_domain_count || 0}</div>
                      <div className="text-xs text-muted-foreground">Apex domains</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-white">{asset.total_subdomains || 0}</div>
                      <div className="text-xs text-muted-foreground">Subdomains</div>
                    </div>
                  </div>

                  {/* Creation Date */}
                  <div className="text-sm text-muted-foreground">
                    Created {new Date(asset.created_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric'
                    })}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Empty State */}
        {assets.length === 0 && (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No assets yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Start by adding your first reconnaissance target asset.
              </p>
              <Button asChild>
                <Link href="/assets/create">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Your First Asset
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Upload Modal */}
      {uploadAsset && (
        <DomainUploadModal
          isOpen={showUploadModal}
          onClose={handleCloseUploadModal}
          onSuccess={handleUploadSuccess}
          assetId={uploadAsset.id}
          assetName={uploadAsset.name}
        />
      )}

      {/* Confirmation Dialog */}
      <ConfirmDeleteDialog
        isOpen={showDeleteDialog}
        onClose={handleCloseDeleteDialog}
        onConfirm={handleConfirmDelete}
        title="Delete Asset"
        assetName={assetToDelete?.name || ''}
        isLoading={deletingAssetId === assetToDelete?.id}
      />
    </div>
  );
}
