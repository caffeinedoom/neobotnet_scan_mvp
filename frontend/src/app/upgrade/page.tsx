'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Zap, Check, Lock, Loader2, ArrowRight, Bell, MessageCircle } from 'lucide-react';
import { Input } from '@/components/ui/input';
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
  const [notifyEmail, setNotifyEmail] = useState('');
  const [isSubmittingEmail, setIsSubmittingEmail] = useState(false);
  const [emailSubmitted, setEmailSubmitted] = useState(false);

  // Discord invite link - replace with your actual Discord invite
  const DISCORD_INVITE_URL = 'https://discord.gg/neobotnet';

  // Redirect unauthenticated users to login
  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/auth/login?redirect=/upgrade');
    }
  }, [authLoading, user, router]);

  // Load billing data once authenticated
  useEffect(() => {
    async function loadData() {
      if (!user) return;
      
      try {
        const [spots, status] = await Promise.all([
          getSpotsRemaining(),
          getBillingStatus()
        ]);
        setSpotsRemaining(spots);
        setBillingStatus(status);
      } catch (error) {
        console.error('Failed to load billing data:', error);
      } finally {
        setIsLoading(false);
      }
    }

    if (!authLoading && user) {
      loadData();
    }
  }, [user, authLoading]);

  const handleNotifySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!notifyEmail || !notifyEmail.includes('@')) {
      toast.error('Please enter a valid email address');
      return;
    }

    setIsSubmittingEmail(true);
    try {
      // For now, just store in localStorage as a simple solution
      // TODO: Implement backend endpoint to store waitlist emails
      const waitlist = JSON.parse(localStorage.getItem('neobotnet_waitlist') || '[]');
      if (!waitlist.includes(notifyEmail)) {
        waitlist.push(notifyEmail);
        localStorage.setItem('neobotnet_waitlist', JSON.stringify(waitlist));
      }
      
      setEmailSubmitted(true);
      toast.success('You\'re on the list! We\'ll notify you when spots open up.');
    } catch (error) {
      console.error('Failed to submit email:', error);
      toast.error('Failed to submit. Please try again.');
    } finally {
      setIsSubmittingEmail(false);
    }
  };

  const handleUpgrade = async () => {
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
  const maxSpots = spotsRemaining?.max_spots ?? 100;

  // Sold out state
  if (spotsLeft <= 0) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto px-4 py-16 max-w-xl">
          {/* Header */}
          <div className="text-center mb-10">
            <h1 className="text-3xl md:text-4xl font-bold mb-4">
              <span className="text-white">Early Adopter Batch</span>{' '}
              <span className="text-[--terminal-green]">Sold Out!</span>
            </h1>
            <p className="text-white/80 text-lg">
              All {maxSpots} early adopter spots have been claimed.
            </p>
          </div>

          {/* Sold Out Card */}
          <Card className="border-white/20 bg-card/50">
            <CardHeader className="text-center pb-4">
              <div className="mx-auto w-16 h-16 rounded-full bg-white/10 flex items-center justify-center mb-4">
                <Lock className="h-8 w-8 text-white/70" />
              </div>
              <CardTitle className="text-xl text-white">Join the Waitlist</CardTitle>
              <CardDescription className="text-white/70 mt-2">
                We&apos;re preparing the next batch of early adopter spots. Be the first to know when they&apos;re available!
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Discord CTA */}
              <div className="bg-[#5865F2]/10 border border-[#5865F2]/30 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <MessageCircle className="h-6 w-6 text-[#5865F2] flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-white mb-1">Join our Discord</h3>
                    <p className="text-sm text-white/70 mb-3">
                      Get instant updates when new spots open up, connect with the community, and get priority access.
                    </p>
                    <a
                      href={DISCORD_INVITE_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 bg-[#5865F2] text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-[#4752C4] transition-colors"
                    >
                      <MessageCircle className="h-4 w-4" />
                      Join Discord Server
                    </a>
                  </div>
                </div>
              </div>

              {/* Email Notification */}
              <div className="border border-white/20 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <Bell className="h-6 w-6 text-[--terminal-green] flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-white mb-1">Get notified by email</h3>
                    <p className="text-sm text-white/70 mb-3">
                      We&apos;ll send you an email when the next batch of spots is ready.
                    </p>
                    {emailSubmitted ? (
                      <div className="flex items-center gap-2 text-[--terminal-green]">
                        <Check className="h-5 w-5" />
                        <span className="text-sm font-medium">You&apos;re on the list!</span>
                      </div>
                    ) : (
                      <form onSubmit={handleNotifySubmit} className="flex gap-2">
                        <Input
                          type="email"
                          placeholder="your@email.com"
                          value={notifyEmail}
                          onChange={(e) => setNotifyEmail(e.target.value)}
                          className="flex-1 bg-black/50 border-white/20 text-white placeholder:text-white/40"
                          disabled={isSubmittingEmail}
                        />
                        <Button
                          type="submit"
                          disabled={isSubmittingEmail}
                          className="bg-white text-black hover:bg-white/90"
                        >
                          {isSubmittingEmail ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            'Notify Me'
                          )}
                        </Button>
                      </form>
                    )}
                  </div>
                </div>
              </div>

              {/* What you'll get */}
              <div className="pt-4 border-t border-white/10">
                <p className="text-xs text-white/50 text-center">
                  Early adopters get lifetime access for just $13.37 — no subscriptions, ever.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

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
            {spotsLeft}/{maxSpots} spots available
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
