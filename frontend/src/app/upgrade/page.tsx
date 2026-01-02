'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Zap, Check, Lock, Loader2, ArrowRight } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
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

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-16 max-w-xl">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-3xl md:text-4xl font-bold mb-4">
            Lifetime Access for <span className="text-[--terminal-green]">Early Adopters</span>
          </h1>
          <p className="text-white/90 text-lg mb-4">
            Pay once, use forever. No subscriptions, no recurring fees.
          </p>
          <p className="text-sm text-white/70 font-mono">
            {spotsLeft}/100 spots available
          </p>
        </div>

        {/* Pricing Card */}
        <Card className="border-[--terminal-green]/50 bg-gradient-to-b from-[--terminal-green]/5 to-transparent">
          <CardHeader className="text-center pb-4">
            <div className="mx-auto w-12 h-12 rounded-full bg-[--terminal-green]/20 flex items-center justify-center mb-4">
              <Zap className="h-6 w-6 text-[--terminal-green]" />
            </div>
            <CardTitle className="text-xl">Early Adopter</CardTitle>
            <div className="mt-4">
              <span className="text-5xl font-bold text-[--terminal-green]">$13.37</span>
              <span className="text-muted-foreground ml-2">one-time</span>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Features */}
            <ul className="space-y-3">
              {[
                'Unlimited URL access',
                '100 API requests per minute',
                'Full data export (CSV/JSON)',
                'Priority support',
              ].map((feature, i) => (
                <li key={i} className="flex items-center gap-3">
                  <Check className="h-5 w-5 text-[--terminal-green] flex-shrink-0" />
                  <span className="text-sm">{feature}</span>
                </li>
              ))}
            </ul>

            {/* CTA Button with animated border */}
            <div className="relative group w-full">
              {/* Animated border wrapper */}
              <div className="absolute -inset-[2px] rounded-lg bg-[conic-gradient(from_var(--angle),transparent_0%,white_10%,transparent_20%)] animate-[spin_3s_linear_infinite] [--angle:0deg]" 
                   style={{ 
                     animation: 'border-spin 3s linear infinite',
                   }} 
              />
              {/* Static white border underneath */}
              <div className="absolute -inset-[2px] rounded-lg border-2 border-white/40" />
              {/* Button */}
              <Button
                onClick={handleUpgrade}
                disabled={isCheckingOut || spotsLeft <= 0}
                className="relative w-full bg-black text-white hover:bg-black/80 h-14 text-lg font-semibold rounded-lg border-0"
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
                    Sign in to continue
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </>
                ) : (
                  <>
                    Become an Early Adopter — $13.37
                  </>
                )}
              </Button>
            </div>
            {/* CSS for animated border */}
            <style jsx>{`
              @keyframes border-spin {
                from { --angle: 0deg; }
                to { --angle: 360deg; }
              }
              @property --angle {
                syntax: '<angle>';
                initial-value: 0deg;
                inherits: false;
              }
            `}</style>

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
      </div>
    </div>
  );
}
