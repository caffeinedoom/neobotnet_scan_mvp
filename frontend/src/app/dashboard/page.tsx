'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { User, Mail, Calendar, CheckCircle, Building2, Globe, Search, Activity } from 'lucide-react';

// Import unified reconnaissance data service
import { reconDataService, type ReconSummary } from '@/lib/api/recon-data';

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();
  
  // State for managing the UI
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<ReconSummary>({
    total_assets: 0,
    active_assets: 0,
    total_domains: 0,
    active_domains: 0,
    total_scans: 0,
    completed_scans: 0,
    failed_scans: 0,
    pending_scans: 0,
    total_subdomains: 0,
    total_probes: 0,
    last_scan_date: undefined
  });

  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      // Only redirect if we're not already on an auth page to prevent infinite loops
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Load dashboard statistics using unified data service
  const loadStats = async () => {
    try {
      setLoading(true);
      
      // UNIFIED DATA SERVICE: Single query serves all recon pages
      // Features: Smart caching, data consistency, O(1) performance
      const dashboardStats = await reconDataService.getDashboardData();
      
      setStats(dashboardStats);
    } catch (error) {
      console.error('Failed to load dashboard stats:', error);
      // Fallback to empty stats on error
      setStats({
        total_assets: 0,
        active_assets: 0,
        total_domains: 0,
        active_domains: 0,
        total_scans: 0,
        completed_scans: 0,
        failed_scans: 0,
        pending_scans: 0,
        total_subdomains: 0,
        total_probes: 0,
        last_scan_date: undefined
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadStats();
    }
  }, [isAuthenticated]);

  if (!isAuthenticated && !isLoading) {
    return null; // Will redirect
  }

  // Show main dashboard
  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Welcome Section */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Dashboard Overview
          </h1>
          <p className="text-muted-foreground mt-2">
            Monitor your reconnaissance framework activity and manage your bug bounty assets.
          </p>
        </div>

        {/* Overview Statistics */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Assets</CardTitle>
              <Building2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12 mb-2" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_assets}</div>
              )}
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-3 bg-muted animate-pulse rounded w-20" />
              ) : (
                <p className="text-xs text-muted-foreground">Bug bounty targets</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Domains</CardTitle>
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
                <p className="text-xs text-muted-foreground">Apex domains</p>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Subdomains</CardTitle>
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
                <p className="text-xs text-muted-foreground">Total discovered</p>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Scans</CardTitle>
              <Activity className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-8 bg-muted animate-pulse rounded w-12 mb-2" />
              ) : (
                <div className="text-2xl font-bold">{stats.pending_scans}</div>
              )}
              {loading || isLoading || !isAuthenticated ? (
                <div className="h-3 bg-muted animate-pulse rounded w-20" />
              ) : (
                <p className="text-xs text-muted-foreground">Running/pending</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => router.push('/assets')}>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Building2 className="h-5 w-5 text-blue-500" />
                <span>Manage Assets</span>
              </CardTitle>
              <CardDescription>
                Create and organize your bug bounty targets and apex domains.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {stats.total_assets > 0 
                  ? `${stats.total_assets} assets with ${stats.total_domains} domains configured`
                  : 'Start by creating your first asset'
                }
              </p>
            </CardContent>
          </Card>

          <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => router.push('/scans')}>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Search className="h-5 w-5 text-purple-500" />
                <span>Start Reconnaissance</span>
              </CardTitle>
              <CardDescription>
                Perform subdomain enumeration and attack surface discovery.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {stats.total_scans > 0 
                  ? `${stats.completed_scans} completed scans, ${stats.pending_scans} active`
                  : 'Begin your first reconnaissance scan'
                }
              </p>
            </CardContent>
          </Card>

          <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => router.push('/subdomains')}>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Globe className="h-5 w-5 text-green-500" />
                <span>View Results</span>
              </CardTitle>
              <CardDescription>
                Browse discovered subdomains and analyze findings.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {stats.total_subdomains > 0 
                  ? `${stats.total_subdomains} subdomains discovered across all scans`
                  : 'Subdomain results will appear here'
                }
              </p>
            </CardContent>
          </Card>
        </div>

        {/* User Profile Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <User className="h-5 w-5" />
              <span>Account Information</span>
            </CardTitle>
            <CardDescription>
              Your profile details and account status
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              <div className="flex items-center space-x-2">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Email:</span>
                <span className="text-sm">{user?.email}</span>
              </div>
              
              {user?.user_metadata?.full_name && (
                <div className="flex items-center space-x-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Name:</span>
                  <span className="text-sm">{user.user_metadata.full_name}</span>
                </div>
              )}
              
              <div className="flex items-center space-x-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Member since:</span>
                <span className="text-sm">
                  {new Date(user?.created_at || '').toLocaleDateString()}
                </span>
              </div>
              
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Status:</span>
                <Badge variant={user?.email_confirmed_at ? "default" : "secondary"}>
                  {user?.email_confirmed_at ? "Email Verified" : "Email Pending"}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 