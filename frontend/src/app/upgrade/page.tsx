'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Zap, Check, Lock, Loader2, ArrowRight } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { getBillingStatus, createCheckoutSession, getSpotsRemaining, BillingStatus, SpotsRemaining } from '@/lib/api/billing';
import { toast } from 'sonner';

export default function UpgradePage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [spotsRemaining, setSpotsRemaining] = useState<SpotsRemaining | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCheckingOut, setIsCheckingOut] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        const spots = await getSpotsRemaining();
        setSpotsRemaining(spots);

        if (user) {
          const status = await getBillingStatus();
          setBillingStatus(status);
        }
      } catch (error) {
        console.error('Failed to load billing data:', error);
      } finally {
        setIsLoading(false);
      }
    }

    if (!authLoading) {
      loadData();
    }
  }, [user, authLoading]);

  const handleUpgrade = async () => {
    if (!user) {
      router.push('/auth/login?redirect=/upgrade');
      return;
    }

    if (billingStatus?.is_paid) {
      toast.info('You already have full access!');
      return;
    }

    if (!spotsRemaining || spotsRemaining.spots_remaining <= 0) {
      toast.error('Sorry, all early access spots have been claimed.');
      return;
    }

    setIsCheckingOut(true);
    try {
      const successUrl = `${window.location.origin}/upgrade/success`;
      const cancelUrl = `${window.location.origin}/upgrade/cancel`;
      
      const session = await createCheckoutSession(successUrl, cancelUrl);
      
      // Redirect to Stripe Checkout
      window.location.href = session.checkout_url;
    } catch (error) {
      console.error('Checkout error:', error);
      toast.error('Failed to start checkout. Please try again.');
      setIsCheckingOut(false);
    }
  };

  if (authLoading || isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[--terminal-green]" />
      </div>
    );
  }

  // Already paid
  if (billingStatus?.is_paid) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto px-4 py-16 max-w-2xl">
          <Card className="border-[--terminal-green]/30 bg-card/50">
            <CardHeader className="text-center">
              <div className="mx-auto w-16 h-16 rounded-full bg-[--terminal-green]/20 flex items-center justify-center mb-4">
                <Check className="h-8 w-8 text-[--terminal-green]" />
              </div>
              <CardTitle className="text-2xl">You Have Full Access</CardTitle>
              <CardDescription>
                Thank you for supporting neobotnet! You have unlimited access to all URLs.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-center">
              <Button onClick={() => router.push('/urls')} className="bg-[--terminal-green] text-black hover:bg-[--terminal-green]/90">
                Browse URLs <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const spotsLeft = spotsRemaining?.spots_remaining ?? 100;
  const urgencyLevel = spotsLeft <= 20 ? 'high' : spotsLeft <= 50 ? 'medium' : 'low';

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-16 max-w-4xl">
        {/* Header */}
        <div className="text-center mb-12">
          <Badge 
            variant="outline" 
            className={`mb-4 ${
              urgencyLevel === 'high' 
                ? 'border-red-500 text-red-400 animate-pulse' 
                : urgencyLevel === 'medium'
                ? 'border-yellow-500 text-yellow-400'
                : 'border-[--terminal-green] text-[--terminal-green]'
            }`}
          >
            {spotsLeft} of 100 spots remaining
          </Badge>
          <h1 className="text-4xl font-bold mb-4">
            Unlock <span className="text-[--terminal-green]">Unlimited URLs</span>
          </h1>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Get full access to all discovered URLs, endpoints, and parameters. 
            One-time payment, lifetime access.
          </p>
        </div>

        {/* Pricing Card */}
        <Card className="border-[--terminal-green]/50 bg-gradient-to-b from-[--terminal-green]/5 to-transparent max-w-md mx-auto">
          <CardHeader className="text-center pb-4">
            <div className="mx-auto w-12 h-12 rounded-full bg-[--terminal-green]/20 flex items-center justify-center mb-4">
              <Zap className="h-6 w-6 text-[--terminal-green]" />
            </div>
            <CardTitle className="text-xl">Early Supporter</CardTitle>
            <div className="mt-4">
              <span className="text-5xl font-bold text-[--terminal-green]">$13.37</span>
              <span className="text-muted-foreground ml-2">one-time</span>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Features */}
            <ul className="space-y-3">
              {[
                'Unlimited URL access (no 250 limit)',
                '100 API requests per minute (vs 30)',
                'All discovered endpoints & parameters',
                'Historical URLs from Wayback Machine',
                'Export to CSV/JSON without limits',
                'Priority support',
              ].map((feature, i) => (
                <li key={i} className="flex items-center gap-3">
                  <Check className="h-5 w-5 text-[--terminal-green] flex-shrink-0" />
                  <span className="text-sm">{feature}</span>
                </li>
              ))}
            </ul>

            {/* CTA Button */}
            <Button
              onClick={handleUpgrade}
              disabled={isCheckingOut || spotsLeft <= 0}
              className="w-full bg-[--terminal-green] text-black hover:bg-[--terminal-green]/90 h-12 text-lg font-semibold"
            >
              {isCheckingOut ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Redirecting to checkout...
                </>
              ) : spotsLeft <= 0 ? (
                <>
                  <Lock className="mr-2 h-5 w-5" />
                  Sold Out
                </>
              ) : !user ? (
                <>
                  Sign in to upgrade
                  <ArrowRight className="ml-2 h-5 w-5" />
                </>
              ) : (
                <>
                  Upgrade Now
                  <ArrowRight className="ml-2 h-5 w-5" />
                </>
              )}
            </Button>

            {/* Trust badges */}
            <div className="flex items-center justify-center gap-4 text-xs text-muted-foreground pt-2">
              <span className="flex items-center gap-1">
                <Lock className="h-3 w-3" /> Secure checkout
              </span>
              <span>•</span>
              <span>Powered by Stripe</span>
            </div>
          </CardContent>
        </Card>

        {/* FAQ / Comparison */}
        <div className="mt-16 grid md:grid-cols-2 gap-8">
          <Card className="border-border/50 bg-card/30">
            <CardHeader>
              <CardTitle className="text-lg">Free Tier</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>✓ Unlimited subdomains</p>
              <p>✓ Unlimited DNS records</p>
              <p>✓ Unlimited web servers</p>
              <p className="text-yellow-400">⚠ 250 URLs limit</p>
              <p>30 API requests/minute</p>
            </CardContent>
          </Card>

          <Card className="border-[--terminal-green]/30 bg-[--terminal-green]/5">
            <CardHeader>
              <CardTitle className="text-lg text-[--terminal-green]">Early Supporter</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>✓ Unlimited subdomains</p>
              <p>✓ Unlimited DNS records</p>
              <p>✓ Unlimited web servers</p>
              <p className="text-[--terminal-green] font-semibold">✓ Unlimited URLs</p>
              <p className="text-[--terminal-green]">100 API requests/minute</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
