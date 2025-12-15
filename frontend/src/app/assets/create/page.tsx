'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
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
import { assetAPI, type AssetCreateRequest } from '@/lib/api/assets';

interface AssetFormData {
  name: string;
  description: string;
}

export default function CreateAssetPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  
  // Form state - simplified to only essential fields
  const [formData, setFormData] = useState<AssetFormData>({
    name: '',
    description: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

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

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    // Only name is required now
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
    
    setLoading(true);
    
    try {
      // Prepare minimal data for API - only essential fields
      const createData: AssetCreateRequest = {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined // Only send description if provided
        // All other fields (priority, tags, is_active) will use backend defaults
      };
      
      // Create asset via API
      await assetAPI.createAsset(createData);
      
      // Redirect to assets list
      router.push('/assets');
    } catch (error: unknown) {
      console.error('Failed to create asset:', error);
      
      // Handle specific API errors
      const apiError = error as { status?: number; message?: string };
      if (apiError.status === 400) {
        setErrors({ submit: 'Invalid asset data. Please check your inputs.' });
      } else if (apiError.status === 403) {
        setErrors({ submit: 'You have reached your asset limit.' });
      } else {
        setErrors({ submit: apiError.message || 'Failed to create asset. Please try again.' });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center space-x-4">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/assets">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Assets
            </Link>
          </Button>
        </div>

        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Create New Asset
          </h1>
          <p className="text-muted-foreground mt-2">
            Add a new reconnaissance target to your portfolio.
          </p>
        </div>

        {/* Simplified Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Building2 className="h-5 w-5" />
              <span>Asset Information</span>
            </CardTitle>
            <CardDescription>
              Define your reconnaissance target with just the essentials.
            </CardDescription>
          </CardHeader>
          
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Asset Name - Required */}
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

              {/* Description - Optional */}
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
                <p className="text-xs text-muted-foreground">
                  Add context about this asset when helpful for your team.
                </p>
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

              {/* Submit Button */}
              <div className="flex space-x-3">
                <Button type="submit" disabled={loading} className="flex-1">
                  {loading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  {loading ? 'Creating...' : 'Create Asset'}
                </Button>
                <Button type="button" variant="outline" asChild>
                  <Link href="/assets">Cancel</Link>
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
