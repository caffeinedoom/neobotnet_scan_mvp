'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckCircle2, ArrowRight, Sparkles, Loader2, AlertTriangle, RefreshCw } from 'lucide-react';
import confetti from 'canvas-confetti';
import { getBillingStatus, BillingStatus } from '@/lib/api/billing';
import { useAuth } from '@/contexts/AuthContext';

export default function UpgradeSuccessPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [showContent, setShowContent] = useState(false);
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [verificationAttempts, setVerificationAttempts] = useState(0);
  const [isVerifying, setIsVerifying] = useState(true);
  const [verificationFailed, setVerificationFailed] = useState(false);

  // Verify the upgrade actually happened
  useEffect(() => {
    async function verifyUpgrade() {
      if (!user) {
        // Wait for auth to load
        return;
      }
      
      try {
        const status = await getBillingStatus();
        setBillingStatus(status);
        
        if (status.is_paid) {
          // Upgrade confirmed! Show celebration
          setIsVerifying(false);
          triggerConfetti();
        } else if (verificationAttempts < 5) {
          // Webhook might not have arrived yet - retry after delay
          // Stripe webhooks can take a few seconds
          setTimeout(() => {
            setVerificationAttempts(prev => prev + 1);
          }, 2000);
        } else {
          // After 5 attempts (10 seconds), show warning
          setIsVerifying(false);
          setVerificationFailed(true);
        }
      } catch (error) {
        console.error('Failed to verify billing status:', error);
        if (verificationAttempts < 5) {
          setTimeout(() => {
            setVerificationAttempts(prev => prev + 1);
          }, 2000);
        } else {
          setIsVerifying(false);
          setVerificationFailed(true);
        }
      }
    }
    
    verifyUpgrade();
  }, [user, verificationAttempts]);

  function triggerConfetti() {
    const duration = 3000;
    const animationEnd = Date.now() + duration;
    const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 0 };

    function randomInRange(min: number, max: number) {
      return Math.random() * (max - min) + min;
    }

    const interval = setInterval(() => {
      const timeLeft = animationEnd - Date.now();

      if (timeLeft <= 0) {
        clearInterval(interval);
        return;
      }

      const particleCount = 50 * (timeLeft / duration);

      confetti({
        ...defaults,
        particleCount,
        origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 },
        colors: ['#00ff00', '#22c55e', '#4ade80'],
      });
      confetti({
        ...defaults,
        particleCount,
        origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 },
        colors: ['#00ff00', '#22c55e', '#4ade80'],
      });
    }, 250);

    // Show content after confetti starts
    setTimeout(() => setShowContent(true), 500);
  }

  const handleRetryVerification = () => {
    setVerificationAttempts(0);
    setIsVerifying(true);
    setVerificationFailed(false);
  };

  // Loading/verifying state
  if (isVerifying) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="max-w-md w-full border-border/50">
          <CardHeader className="text-center pb-4">
            <div className="mx-auto w-16 h-16 rounded-full bg-[--terminal-green]/20 flex items-center justify-center mb-4">
              <Loader2 className="h-8 w-8 animate-spin text-[--terminal-green]" />
            </div>
            <CardTitle className="text-xl">Confirming your upgrade...</CardTitle>
            <CardDescription className="text-sm mt-2">
              Please wait while we verify your payment.
              {verificationAttempts > 0 && (
                <span className="block mt-1 text-xs">
                  Attempt {verificationAttempts + 1} of 5...
                </span>
              )}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  // Verification failed - show warning with retry option
  if (verificationFailed) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="max-w-md w-full border-yellow-500/50 bg-gradient-to-b from-yellow-500/10 to-transparent">
          <CardHeader className="text-center pb-4">
            <div className="mx-auto w-16 h-16 rounded-full bg-yellow-500/20 flex items-center justify-center mb-4">
              <AlertTriangle className="h-8 w-8 text-yellow-500" />
            </div>
            <CardTitle className="text-xl">Upgrade Processing</CardTitle>
            <CardDescription className="text-sm mt-2">
              Your payment was received, but we&apos;re still processing your upgrade.
              This usually takes a few seconds but can occasionally take longer.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-yellow-500/10 rounded-lg p-4 text-sm">
              <p className="text-yellow-200">
                <strong>Don&apos;t worry!</strong> Your payment is secure. If your upgrade doesn&apos;t appear within a few minutes, 
                please contact support with your payment confirmation email.
              </p>
            </div>
            <div className="space-y-3">
              <Button
                onClick={handleRetryVerification}
                className="w-full bg-yellow-500 text-black hover:bg-yellow-500/90 h-12"
              >
                <RefreshCw className="mr-2 h-5 w-5" />
                Check Again
              </Button>
              <Button
                onClick={() => router.push('/dashboard')}
                variant="outline"
                className="w-full"
              >
                Go to Dashboard
              </Button>
            </div>
            <p className="text-xs text-center text-muted-foreground">
              Receipt: Check your email for payment confirmation.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Success! Show celebration
  if (!showContent) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-[--terminal-green]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="max-w-md w-full border-[--terminal-green]/50 bg-gradient-to-b from-[--terminal-green]/10 to-transparent animate-in fade-in-0 zoom-in-95 duration-500">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto w-20 h-20 rounded-full bg-[--terminal-green]/20 flex items-center justify-center mb-4 animate-bounce">
            <CheckCircle2 className="h-10 w-10 text-[--terminal-green]" />
          </div>
          <CardTitle className="text-2xl flex items-center justify-center gap-2">
            <Sparkles className="h-6 w-6 text-[--terminal-green]" />
            Welcome, Early Supporter!
            <Sparkles className="h-6 w-6 text-[--terminal-green]" />
          </CardTitle>
          <CardDescription className="text-base mt-2">
            Your payment was successful. You now have full access to neobotnet.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* What's unlocked */}
          <div className="bg-[--terminal-green]/5 rounded-lg p-4 space-y-2">
            <h3 className="font-semibold text-[--terminal-green]">What&apos;s unlocked:</h3>
            <ul className="text-sm space-y-1 text-muted-foreground">
              <li>✓ Unlimited URL access</li>
              <li>✓ 100 API requests/minute</li>
              <li>✓ Full export capabilities</li>
              <li>✓ Lifetime access</li>
            </ul>
          </div>

          {/* CTA Buttons */}
          <div className="space-y-3">
            <Button
              onClick={() => router.push('/urls')}
              className="w-full bg-[--terminal-green] text-black hover:bg-[--terminal-green]/90 h-12"
            >
              Explore URLs
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button
              onClick={() => router.push('/dashboard')}
              variant="outline"
              className="w-full border-[--terminal-green]/50 hover:bg-[--terminal-green]/10"
            >
              Go to Dashboard
            </Button>
          </div>

          <p className="text-xs text-center text-muted-foreground">
            A receipt has been sent to your email.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
