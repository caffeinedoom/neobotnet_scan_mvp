'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { 
  Building2, 
  ArrowLeft, 
  Save,
  AlertTriangle
} from 'lucide-react';
import Link from 'next/link';
import { assetAPI, type AssetWithStats, type AssetUpdateRequest } from '@/lib/api/assets';
import { toast } from 'sonner';

interface AssetFormData {
  name: string;
  description: string;
}

export default function EditAssetPage() {
  const router = useRouter();
  const params = useParams();
  const { isAuthenticated, isLoading } = useAuth();
  
  const assetId = params.id as string;
  
  // State management
  const [asset, setAsset] = useState<AssetWithStats | null>(null);
  const [formData, setFormData] = useState<AssetFormData>({
    name: '',
    description: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Load asset data
  useEffect(() => {
    const loadAsset = async () => {
      try {
        setLoading(true);
        const assetData = await assetAPI.getAsset(assetId);
        setAsset(assetData);
        setFormData({
          name: assetData.name,
          description: assetData.description || ''
        });
      } catch (error) {
        console.error('Failed to load asset:', error);
        toast.error('Failed to load asset');
        router.push(`/assets/${assetId}`);
      } finally {
        setLoading(false);
      }
    };

    if (isAuthenticated && assetId) {
      loadAsset();
    }
  }, [isAuthenticated, assetId, router]);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      // Only redirect if we're not already on an auth page to prevent infinite loops
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

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
        <div className="max-w-2xl mx-auto space-y-6">
          <div className="h-8 bg-muted animate-pulse rounded" />
          <div className="h-64 bg-muted animate-pulse rounded" />
        </div>
      </div>
    );
  }

  if (!asset) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="max-w-2xl mx-auto text-center">
          <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">Asset not found</h3>
          <p className="text-muted-foreground mb-4">
            The asset you&apos;re trying to edit doesn&apos;t exist or has been removed.
          </p>
          <Button asChild>
            <Link href="/assets">Back to Assets</Link>
          </Button>
        </div>
      </div>
    );
  }

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Asset name is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setSaving(true);
    
    try {
      const updateData: AssetUpdateRequest = {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined
      };
      
      await assetAPI.updateAsset(assetId, updateData);
      toast.success('Asset updated successfully');
      router.push(`/assets/${assetId}`);
    } catch (error: unknown) {
      console.error('Failed to update asset:', error);
      
      const apiError = error as { status?: number; message?: string };
      if (apiError.status === 400) {
        setErrors({ submit: 'Invalid asset data. Please check your inputs.' });
      } else {
        setErrors({ submit: apiError.message || 'Failed to update asset. Please try again.' });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center space-x-4">
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/assets/${assetId}`}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Asset
            </Link>
          </Button>
        </div>

        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Edit Asset
          </h1>
          <p className="text-muted-foreground mt-2">
            Update your asset information.
          </p>
        </div>

        {/* Edit Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Building2 className="h-5 w-5" />
              <span>Asset Information</span>
            </CardTitle>
            <CardDescription>
              Update the basic information for this asset.
            </CardDescription>
          </CardHeader>
          
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Asset Name */}
              <div className="space-y-2">
                <Label htmlFor="name">Asset Name *</Label>
                <Input
                  id="name"
                  placeholder="e.g., E-Corp"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={errors.name ? 'border-destructive' : ''}
                />
                {errors.name && (
                  <p className="text-sm text-destructive flex items-center space-x-1">
                    <AlertTriangle className="h-4 w-4" />
                    <span>{errors.name}</span>
                  </p>
                )}
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="description">Description <span className="text-muted-foreground">(optional)</span></Label>
                <textarea
                  id="description"
                  placeholder="Brief description of the asset..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  rows={3}
                />
              </div>

              {/* Submit Error */}
              {errors.submit && (
                <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20">
                  <p className="text-sm text-destructive flex items-center space-x-1">
                    <AlertTriangle className="h-4 w-4" />
                    <span>{errors.submit}</span>
                  </p>
                </div>
              )}

              {/* Submit Buttons */}
              <div className="flex space-x-3">
                <Button type="submit" disabled={saving} className="flex-1">
                  {saving ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
                <Button type="button" variant="outline" asChild>
                  <Link href={`/assets/${assetId}`}>Cancel</Link>
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
