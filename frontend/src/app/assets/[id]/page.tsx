'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { 
  Building2, 
  ArrowLeft, 
  Plus,
  Globe,
  Search,
  Calendar,
  Edit,
  Trash2,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Upload,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import Link from 'next/link';
import { assetAPI, type ApexDomainWithStats, type ApexDomainCreateRequest, type PaginatedDomainsResponse } from '@/lib/api/assets';
import { toast } from 'sonner';
import { ConfirmDeleteDialog } from '@/components/ui/confirm-delete-dialog';
import { DomainUploadModal } from '@/components/ui/domain-upload-modal';

// ================================================================
// UNIFIED DATA SERVICE: Use same counting logic as dashboard/assets  
// ================================================================
import { reconDataService, type ReconAsset } from '@/lib/api/recon-data';

// Use API types directly - no need for custom interfaces
type Domain = ApexDomainWithStats;

export default function AssetDetailPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();
  
  const assetId = params.id as string;
  
  // ================================================================
  // NEW: URL-Driven State Management (Phase 2a)
  // ================================================================
  
  // Domain pagination state from URL
  const domainPage = parseInt(searchParams.get('domain_page') || '1');
  const domainPerPage = parseInt(searchParams.get('domain_per_page') || '10');
  const domainSearch = searchParams.get('domain_search') || '';
  const domainFilter = searchParams.get('domain_filter'); // 'active', 'inactive', or null for all
  
  // State management
  const [asset, setAsset] = useState<ReconAsset | null>(null);
  const [domainData, setDomainData] = useState<PaginatedDomainsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [domainLoading, setDomainLoading] = useState(false);
  const [newDomain, setNewDomain] = useState('');
  const [addingDomain, setAddingDomain] = useState(false);
  const [deletingAsset, setDeletingAsset] = useState(false);
  const [showConfirmDeleteDialog, setShowConfirmDeleteDialog] = useState(false);
  
  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState(false);
  
  // ================================================================
  // NEW: URL Update Helper (Seamless Navigation)
  // ================================================================

  const updateDomainURL = useCallback((updates: Record<string, string | number | null>) => {
    const newParams = new URLSearchParams(searchParams.toString());
    
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === '' || (key === 'domain_filter' && value === 'all')) {
        newParams.delete(key);
      } else {
        newParams.set(key, value.toString());
      }
    });

    // Use replace for seamless navigation
    router.replace(`/assets/${assetId}?${newParams.toString()}`, { scroll: false });
  }, [router, searchParams, assetId]);

  // ================================================================
  // NEW: Efficient Domain Loading
  // ================================================================

  const loadDomains = useCallback(async () => {
    if (!isAuthenticated) return;
    
    try {
      setDomainLoading(true);
      
      const response = await assetAPI.getPaginatedAssetDomains(assetId, {
        page: domainPage,
        per_page: domainPerPage,
        is_active: domainFilter === 'active' ? true : domainFilter === 'inactive' ? false : undefined,
        search: domainSearch || undefined,
      });
      
      setDomainData(response);
      
    } catch (error) {
      console.error('Failed to load domains:', error);
      toast.error('Failed to load domains');
    } finally {
      setDomainLoading(false);
    }
  }, [isAuthenticated, assetId, domainPage, domainPerPage, domainFilter, domainSearch]);

  // Load asset details using UNIFIED service (same logic as dashboard/assets)
  const loadAssetData = useCallback(async () => {
    try {
      setLoading(true);
      const assetResponse = await reconDataService.getAssetDetailData(assetId);
      setAsset(assetResponse);
    } catch (error) {
      console.error('Failed to load asset data:', error);
      toast.error('Failed to load asset data');
    } finally {
      setLoading(false);
    }
  }, [assetId]);

  // ================================================================
  // NEW: Simplified Event Handlers (URL-driven)
  // ================================================================

  // Domain search and filter handlers removed - using direct URL updates for now
  // TODO: Re-implement if search/filter functionality is needed

  const handleDomainPageChange = (newPage: number) => {
    updateDomainURL({ domain_page: newPage });
  };

  const handleDomainPerPageChange = (newPerPage: number) => {
    updateDomainURL({ domain_per_page: newPerPage, domain_page: 1 });
  };

  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      // Only redirect if we're not already on an auth page to prevent infinite loops
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (isAuthenticated) {
      loadAssetData();
      loadDomains();
    }
  }, [isAuthenticated, loadAssetData, loadDomains]);

  // ================================================================
  // SIMPLIFIED: Domain Management (No Optimistic Updates)
  // ================================================================

  const addDomain = async () => {
    if (!newDomain.trim()) return;
    
    const domainName = newDomain.trim();
    
    try {
      setAddingDomain(true);
      setNewDomain('');
      
      const domainData: ApexDomainCreateRequest = {
        domain: domainName
      };
      
      await assetAPI.createApexDomain(assetId, domainData);
      toast.success('Domain added successfully');
      
      // Refresh domains after successful addition
      await loadDomains();
      
    } catch (error) {
      console.error('Failed to add domain:', error);
      toast.error('Failed to add domain');
      setNewDomain(domainName); // Restore the input on error
    } finally {
      setAddingDomain(false);
    }
  };

  const handleDomainAction = async (domainId: string, action: 'scan' | 'delete') => {
    try {
      switch (action) {
        case 'scan':
          toast.info('Scan functionality coming soon');
          break;
        case 'delete':
          await assetAPI.deleteApexDomain(assetId, domainId);
          toast.success('Domain deleted successfully');
          
          // Refresh domains after successful deletion
          await loadDomains();
          break;
      }
    } catch (error) {
      console.error(`Failed to ${action} domain:`, error);
      toast.error(`Failed to ${action} domain`);
    }
  };

  // Modal handlers for domain upload
  const handleUploadSuccess = async () => {
    // Refresh domains list after successful upload
    await loadDomains();
  };

  const handleCloseUploadModal = () => {
    setShowUploadModal(false);
  };

  // Handle asset deletion with confirmation
  const handleDeleteAsset = async () => {
    if (!asset) return;

    setDeletingAsset(true);
    try {
      await assetAPI.deleteAsset(assetId);
      toast.success(`Asset "${asset.name}" deleted successfully`);
      router.push('/assets');
    } catch (error) {
      console.error('Failed to delete asset:', error);
      toast.error(`Failed to delete asset "${asset.name}"`);
    } finally {
      setDeletingAsset(false);
      setShowConfirmDeleteDialog(false);
    }
  };

  const getStatusIcon = (isActive: boolean) => {
    return isActive ? 
      <CheckCircle className="h-4 w-4 text-green-500" /> : 
      <AlertTriangle className="h-4 w-4 text-muted-foreground" />;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="max-w-6xl mx-auto space-y-6">
          <div className="h-8 bg-muted animate-pulse rounded" />
          <div className="h-48 bg-muted animate-pulse rounded" />
          <div className="h-64 bg-muted animate-pulse rounded" />
        </div>
      </div>
    );
  }

  if (!asset) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="max-w-6xl mx-auto text-center">
          <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">Asset not found</h3>
          <p className="text-muted-foreground mb-4">
            The asset you&apos;re looking for doesn&apos;t exist or has been removed.
          </p>
          <Button asChild>
            <Link href="/assets">Back to Assets</Link>
          </Button>
        </div>
      </div>
    );
  }

  // Calculate stats from real data
  const totalScans = asset.total_scans || 0;
  const totalSubdomains = asset.total_subdomains || 0;

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center space-x-4">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/assets">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Assets
            </Link>
          </Button>
        </div>

        {/* Asset Overview - Simplified */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <Building2 className="h-6 w-6" />
                  <CardTitle className="text-2xl">{asset.name}</CardTitle>
                  <Badge variant={asset.is_active ? "default" : "secondary"}>
                    {asset.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                {asset.description && (
                  <CardDescription>{asset.description}</CardDescription>
                )}
              </div>
              
              <div className="flex space-x-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="hover:bg-slate-50 hover:text-slate-700 hover:border-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-200 dark:hover:border-slate-600"
                  asChild
                >
                  <Link href={`/assets/${assetId}/edit`}>
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </Link>
                </Button>
                
                <Button 
                  variant="outline" 
                  size="sm"
                  className="hover:bg-red-50 hover:text-red-600 hover:border-red-200"
                  onClick={() => setShowConfirmDeleteDialog(true)}
                  disabled={deletingAsset}
                >
                  {deletingAsset ? (
                    <div className="h-4 w-4 mr-2 animate-spin rounded-full border-2 border-red-600 border-t-transparent" />
                  ) : (
                    <Trash2 className="h-4 w-4 mr-2" />
                  )}
                  Delete
                </Button>
              </div>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-4">
            {/* Asset Info - Simplified */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Created:</span>
                  <span className="text-sm">{new Date(asset.created_at).toLocaleDateString()}</span>
                </div>
              </div>
              
              {/* Stats - Using real data */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-lg font-semibold">{domainData?.pagination.total || 0}</div>
                  <div className="text-xs text-muted-foreground">Domains</div>
                </div>
                <div>
                  <div className="text-lg font-semibold">{totalScans}</div>
                  <div className="text-xs text-muted-foreground">Scans</div>
                </div>
                <div>
                  <div className="text-lg font-semibold">{totalSubdomains}</div>
                  <div className="text-xs text-muted-foreground">Subdomains</div>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex space-x-2 pt-4 border-t">
              <Button asChild className="flex-1">
                <Link href={`/subdomains?asset=${asset.id}&page=1&per_page=50`}>
                  <Search className="h-4 w-4 mr-2" />
                  View Subdomains ({totalSubdomains})
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href={`/assets/${asset.id}/analytics`}>
                  <TrendingUp className="h-4 w-4 mr-2" />
                  Analytics
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Domain Management */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center space-x-2">
                  <Globe className="h-5 w-5" />
                  <span>Apex Domains ({domainData?.pagination.total || 0})</span>
                </CardTitle>
                <CardDescription>
                  Manage the root domains for reconnaissance scanning.
                </CardDescription>
              </div>
              
              {/* Add Domain Methods */}
              <div className="flex flex-col space-y-4">
                {/* Upload File Button */}
                <div className="flex justify-end">
                  <Button 
                    variant="outline"
                    size="sm"
                    onClick={() => setShowUploadModal(true)}
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    Upload File
                  </Button>
                </div>

                {/* Single Domain Input */}
                <div className="flex space-x-2">
                  <Input
                    placeholder="Enter domain (e.g., example.com)"
                    value={newDomain}
                    onChange={(e) => setNewDomain(e.target.value)}
                    className="w-64"
                    onKeyPress={(e) => e.key === 'Enter' && addDomain()}
                  />
                  <Button onClick={addDomain} disabled={addingDomain}>
                    {addingDomain ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                    ) : (
                      <Plus className="h-4 w-4 mr-2" />
                    )}
                    Add
                  </Button>
                </div>


              </div>
            </div>
          </CardHeader>
          
          <CardContent>
            {domainLoading ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4" />
                <p>Loading domains...</p>
              </div>
            ) : domainData?.domains.length === 0 ? (
              <div className="text-center py-8">
                <Globe className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">No domains yet</h3>
                <p className="text-muted-foreground">
                  Add apex domains to start reconnaissance scanning.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {domainData?.domains.map((domain: Domain) => (
                  <div 
                    key={domain.id} 
                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center space-x-4">
                      {getStatusIcon(domain.is_active)}
                      <div>
                        <div className="font-medium">{domain.domain}</div>
                        {domain.description && (
                          <div className="text-sm text-muted-foreground">
                            {domain.description}
                          </div>
                        )}
                        <div className="flex items-center space-x-4 text-xs text-muted-foreground mt-1">
                          <span>{domain.total_subdomains || 0} subdomains</span>
                          {domain.last_scan_date && (
                            <span>Last scan: {new Date(domain.last_scan_date).toLocaleDateString()}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDomainAction(domain.id, 'scan')}
                      >
                        <Search className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDomainAction(domain.id, 'delete')}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination Controls */}
            {domainData && domainData.pagination.total_pages > 1 && (
              <div className="flex items-center justify-between px-2 py-4 sm:px-4">
                <div className="flex-1 text-sm text-muted-foreground">
                  Showing {domainData.pagination.page * domainPerPage - domainPerPage + 1} to{' '}
                  {Math.min(domainData.pagination.page * domainPerPage, domainData.pagination.total)} of{' '}
                  {domainData.pagination.total} results
                </div>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="outline"
                    onClick={() => handleDomainPageChange(domainPage - 1)}
                    disabled={domainPage === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm font-medium">Page {domainPage}</span>
                  <Button
                    variant="outline"
                    onClick={() => handleDomainPageChange(domainPage + 1)}
                    disabled={domainPage === domainData.pagination.total_pages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                  <select
                    className="w-20 h-8 text-sm border rounded-md"
                    value={domainPerPage}
                    onChange={(e) => handleDomainPerPageChange(parseInt(e.target.value))}
                  >
                    <option value="10">10</option>
                    <option value="20">20</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                    <option value="250">250</option>
                  </select>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      {/* Upload Modal */}
      <DomainUploadModal
        isOpen={showUploadModal}
        onClose={handleCloseUploadModal}
        onSuccess={handleUploadSuccess}
        assetId={assetId}
        assetName={asset?.name || ''}
      />

      {/* Confirmation Dialog */}
      <ConfirmDeleteDialog
        isOpen={showConfirmDeleteDialog}
        onClose={() => setShowConfirmDeleteDialog(false)}
        onConfirm={handleDeleteAsset}
        title="Delete Asset"
        assetName={asset?.name || ''}
        isLoading={deletingAsset}
      />
    </div>
  );
}
