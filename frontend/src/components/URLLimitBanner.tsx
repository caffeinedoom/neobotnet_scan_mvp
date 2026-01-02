'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Lock, Zap, ArrowRight, Loader2 } from 'lucide-react';
import { getBillingStatus, BillingStatus } from '@/lib/api/billing';
import { useAuth } from '@/context/AuthContext';

interface URLLimitBannerProps {
  className?: string;
}

export function URLLimitBanner({ className = '' }: URLLimitBannerProps) {
  const router = useRouter();
  const { user } = useAuth();
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadStatus() {
      if (!user) {
        setIsLoading(false);
        return;
      }

      try {
        const billingStatus = await getBillingStatus();
        setStatus(billingStatus);
      } catch (error) {
        console.error('Failed to load billing status:', error);
      } finally {
        setIsLoading(false);
      }
    }

    loadStatus();
  }, [user]);

  // Don't show if loading
  if (isLoading) {
    return (
      <div className={`flex items-center justify-center py-3 px-4 bg-muted/30 rounded-lg ${className}`}>
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Don't show for paid users
  if (status?.is_paid) {
    return null;
  }

  // Not logged in
  if (!user) {
    return (
      <div className={`flex items-center justify-between py-3 px-4 bg-amber-500/10 border border-amber-500/30 rounded-lg ${className}`}>
        <div className="flex items-center gap-3">
          <Lock className="h-5 w-5 text-amber-500" />
          <span className="text-sm">
            <span className="font-medium text-amber-400">Sign in</span>
            <span className="text-muted-foreground"> to view URLs</span>
          </span>
        </div>
        <Button
          onClick={() => router.push('/auth/login?redirect=/urls')}
          size="sm"
          className="bg-amber-500 text-black hover:bg-amber-400"
        >
          Sign In
        </Button>
      </div>
    );
  }

  const limit = status?.urls_limit ?? 250;
  const viewed = status?.urls_viewed ?? 0;
  const remaining = status?.urls_remaining ?? limit;
  const percentage = Math.min(100, (viewed / limit) * 100);
  const isNearLimit = remaining <= 50;
  const isAtLimit = remaining <= 0;

  // At limit - upgrade required
  if (isAtLimit) {
    return (
      <div className={`flex flex-col sm:flex-row items-center justify-between gap-4 py-4 px-5 bg-red-500/10 border border-red-500/30 rounded-lg ${className}`}>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-full bg-red-500/20">
            <Lock className="h-5 w-5 text-red-400" />
          </div>
          <div>
            <p className="font-medium text-red-400">URL Limit Reached</p>
            <p className="text-sm text-muted-foreground">
              You&apos;ve viewed all {limit} free URLs. Upgrade for unlimited access.
            </p>
          </div>
        </div>
        <Button
          onClick={() => router.push('/upgrade')}
          className="bg-[--terminal-green] text-black hover:bg-[--terminal-green]/90 whitespace-nowrap"
        >
          <Zap className="mr-2 h-4 w-4" />
          Upgrade $13.37
        </Button>
      </div>
    );
  }

  // Near limit - warning
  if (isNearLimit) {
    return (
      <div className={`flex flex-col sm:flex-row items-center justify-between gap-4 py-3 px-4 bg-amber-500/10 border border-amber-500/30 rounded-lg ${className}`}>
        <div className="flex items-center gap-3 flex-1">
          <Zap className="h-5 w-5 text-amber-400" />
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-amber-400">
                {remaining} URLs remaining
              </span>
              <span className="text-xs text-muted-foreground">
                {viewed}/{limit}
              </span>
            </div>
            <Progress value={percentage} className="h-1.5 bg-muted" />
          </div>
        </div>
        <Button
          onClick={() => router.push('/upgrade')}
          size="sm"
          variant="outline"
          className="border-amber-500/50 text-amber-400 hover:bg-amber-500/10"
        >
          Unlock Unlimited
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    );
  }

  // Normal state - subtle reminder
  return (
    <div className={`flex items-center justify-between py-2 px-4 bg-muted/30 border border-border/50 rounded-lg ${className}`}>
      <div className="flex items-center gap-3 flex-1">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground">
              Free tier: {viewed}/{limit} URLs viewed
            </span>
            <span className="text-xs text-muted-foreground">
              {remaining} remaining
            </span>
          </div>
          <Progress value={percentage} className="h-1 bg-muted" />
        </div>
      </div>
      <Button
        onClick={() => router.push('/upgrade')}
        size="sm"
        variant="ghost"
        className="text-xs text-muted-foreground hover:text-[--terminal-green]"
      >
        Upgrade
      </Button>
    </div>
  );
}
