'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { YouFormEmbed } from '@/components/ui/youform-embed';
import { Globe, Link2, Network, Server } from 'lucide-react';
import { getBillingStatus, type BillingStatus } from '@/lib/api/billing';

// Import unified reconnaissance data service
import { reconDataService, type ReconSummary } from '@/lib/api/recon-data';

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();
  
  // State for managing the UI
  const [loading, setLoading] = useState(true);
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
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
    total_dns_records: 0,
    total_urls: 0,
    last_scan_date: undefined
  });

  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Load dashboard statistics and billing status
  const loadData = async () => {
    try {
      setLoading(true);
      
      const [dashboardStats, billing] = await Promise.all([
        reconDataService.getDashboardData(),
        getBillingStatus().catch(() => null)
      ]);
      
      setStats(dashboardStats);
      setBillingStatus(billing);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated]);

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  const isPro = billingStatus?.is_paid;

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Reconnaissance framework overview
          </p>
        </div>

        {/* Stats Grid - 4 columns */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-card/50 backdrop-blur">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Subdomains</CardTitle>
              <Globe className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-8 bg-muted animate-pulse rounded w-16" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_subdomains.toLocaleString()}</div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">URLs</CardTitle>
              <Link2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-8 bg-muted animate-pulse rounded w-16" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_urls.toLocaleString()}</div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">DNS Records</CardTitle>
              <Network className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-8 bg-muted animate-pulse rounded w-16" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_dns_records.toLocaleString()}</div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Servers</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="h-8 bg-muted animate-pulse rounded w-16" />
              ) : (
                <div className="text-2xl font-bold">{stats.total_probes.toLocaleString()}</div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* User Info Row */}
        <div className="flex items-center justify-between py-4 px-5 rounded-lg border border-border/50 bg-card/30">
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">Signed in as</span>
            <span className="text-sm font-medium">{user?.email}</span>
          </div>
          <Badge 
            variant={isPro ? "default" : "secondary"}
            className={isPro ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" : ""}
          >
            {isPro ? 'PRO' : 'FREE'}
          </Badge>
        </div>

        {/* Divider */}
        <div className="border-t border-border/30" />

        {/* Request a Program Section */}
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-semibold">Request a Program</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Want a specific bug bounty program added to our platform? Submit your request below.
            </p>
          </div>

          {/* YouForm Embed - Direct iframe for reliable SPA navigation */}
          <div className="rounded-lg border border-border/50 bg-card/30 overflow-hidden">
            <YouFormEmbed 
              formId="w99tz8px" 
              height={600}
              title="Request a Program Form"
            />
          </div>
        </div>

      </div>
    </div>
  );
}
