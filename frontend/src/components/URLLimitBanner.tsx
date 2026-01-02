'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Lock, Zap, ArrowRight } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

interface URLQuota {
  plan_type: string;
  urls_limit: number;
  urls_viewed: number;
  urls_remaining: number;
  is_limited: boolean;
  upgrade_required: boolean;
}

interface URLLimitBannerProps {
  quota?: URLQuota | null;
  className?: string;
}

export function URLLimitBanner({ quota, className = '' }: URLLimitBannerProps) {
  const router = useRouter();
  const { user } = useAuth();

  // Don't show for paid users
  if (quota && quota.plan_type !== 'free') {
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

  // No quota data yet - show loading state
  if (!quota) {
    return (
      <div className={`flex items-center justify-between py-2 px-4 bg-muted/30 border border-border/50 rounded-lg ${className}`}>
        <span className="text-xs text-muted-foreground">Loading quota...</span>
      </div>
    );
  }

  const limit = quota.urls_limit ?? 250;
  const viewed = quota.urls_viewed ?? 0;
  const remaining = quota.urls_remaining ?? limit;
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
          className="border-2 border-white bg-transparent text-white font-bold hover:bg-white hover:text-black transition-all"
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
          className="border-2 border-white bg-transparent text-white font-bold hover:bg-white hover:text-black transition-all"
        >
          Upgrade
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    );
  }

  // Normal state - with prominent upgrade button
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
        className="ml-4 border-2 border-white bg-transparent text-white font-bold hover:bg-white hover:text-black transition-all"
      >
        Upgrade
      </Button>
    </div>
  );
}
