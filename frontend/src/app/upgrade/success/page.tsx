'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Check, ArrowRight, Loader2, AlertTriangle, RefreshCw } from 'lucide-react';
import { getBillingStatus, BillingStatus } from '@/lib/api/billing';
import { useAuth } from '@/contexts/AuthContext';

// ============================================================================
// TYPING ANIMATION CONSTANTS
// ============================================================================

const TITLE_TEXT = 'neobotnet';
const TAGLINE_TEXT = 'Thank you, Early Adopter.';

// Benefits matching /upgrade page exactly
const BENEFITS = [
  'Unlimited URL access',
  '100 API requests per minute',
  'Full data export (CSV/JSON)',
  'Priority support',
  'Lifetime access',
];

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function UpgradeSuccessPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();
  
  // Verification state
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [verificationAttempts, setVerificationAttempts] = useState(0);
  const [isVerifying, setIsVerifying] = useState(true);
  const [verificationFailed, setVerificationFailed] = useState(false);
  const [cameFromStripe, setCameFromStripe] = useState(false);
  
  // Animation state
  const [typedTitle, setTypedTitle] = useState('');
  const [typedTagline, setTypedTagline] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const [typingPhase, setTypingPhase] = useState<'waiting' | 'title' | 'tagline' | 'benefits' | 'done'>('waiting');
  const [visibleBenefits, setVisibleBenefits] = useState<number>(0);
  const [showCTA, setShowCTA] = useState(false);

  // ============================================================================
  // AUTH CHECK - Redirect unauthenticated users
  // ============================================================================

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/auth/login?redirect=/upgrade');
    }
  }, [authLoading, user, router]);

  // ============================================================================
  // CHECK IF USER CAME FROM STRIPE (via referrer or session)
  // ============================================================================

  useEffect(() => {
    // Check if user just came from Stripe checkout
    // We give them the benefit of the doubt on first load
    // (they could have come from Stripe's success_url redirect)
    if (typeof window !== 'undefined') {
      const referrer = document.referrer;
      const isFromStripe = referrer.includes('stripe.com') || referrer.includes('checkout.stripe.com');
      // Also check if this is a fresh page load (not a manual navigation)
      const isFirstVisit = !sessionStorage.getItem('upgrade_success_visited');
      
      if (isFirstVisit) {
        sessionStorage.setItem('upgrade_success_visited', 'true');
        setCameFromStripe(true); // Give benefit of doubt on first visit
      } else {
        setCameFromStripe(isFromStripe);
      }
    }
  }, []);

  // ============================================================================
  // VERIFICATION LOGIC
  // ============================================================================

  useEffect(() => {
    async function verifyUpgrade() {
      if (!user) return;
      
      try {
        const status = await getBillingStatus();
        setBillingStatus(status);
        
        if (status.is_paid) {
          // Upgrade confirmed! Start typing animation
          setIsVerifying(false);
          setTypingPhase('title');
        } else if (verificationAttempts < 5) {
          // Webhook might not have arrived yet - retry after delay
          setTimeout(() => {
            setVerificationAttempts(prev => prev + 1);
          }, 2000);
        } else {
          // After 5 attempts (10 seconds):
          // If user didn't come from Stripe, redirect to /upgrade
          // Otherwise show the warning (legitimate payment might be delayed)
          setIsVerifying(false);
          if (cameFromStripe) {
            setVerificationFailed(true);
          } else {
            // User manually navigated here without paying - redirect
            router.replace('/upgrade');
          }
        }
      } catch (error) {
        console.error('Failed to verify billing status:', error);
        if (verificationAttempts < 5) {
          setTimeout(() => {
            setVerificationAttempts(prev => prev + 1);
          }, 2000);
        } else {
          setIsVerifying(false);
          if (cameFromStripe) {
            setVerificationFailed(true);
          } else {
            router.replace('/upgrade');
          }
        }
      }
    }
    
    verifyUpgrade();
  }, [user, verificationAttempts, cameFromStripe, router]);

  // ============================================================================
  // TYPING ANIMATION
  // ============================================================================

  // Title typing
  useEffect(() => {
    if (typingPhase === 'title') {
      if (typedTitle.length < TITLE_TEXT.length) {
        const timeout = setTimeout(() => {
          setTypedTitle(TITLE_TEXT.slice(0, typedTitle.length + 1));
        }, 80);
        return () => clearTimeout(timeout);
      } else {
        // Pause before starting tagline
        const timeout = setTimeout(() => setTypingPhase('tagline'), 400);
        return () => clearTimeout(timeout);
      }
    }
  }, [typedTitle, typingPhase]);

  // Tagline typing
  useEffect(() => {
    if (typingPhase === 'tagline') {
      if (typedTagline.length < TAGLINE_TEXT.length) {
        const timeout = setTimeout(() => {
          setTypedTagline(TAGLINE_TEXT.slice(0, typedTagline.length + 1));
        }, 50);
        return () => clearTimeout(timeout);
      } else {
        // Pause before showing benefits
        const timeout = setTimeout(() => setTypingPhase('benefits'), 500);
        return () => clearTimeout(timeout);
      }
    }
  }, [typedTagline, typingPhase]);

  // Benefits animation (staggered reveal)
  useEffect(() => {
    if (typingPhase === 'benefits') {
      if (visibleBenefits < BENEFITS.length) {
        const timeout = setTimeout(() => {
          setVisibleBenefits(prev => prev + 1);
        }, 150);
        return () => clearTimeout(timeout);
      } else {
        // Show CTA after benefits
        const timeout = setTimeout(() => {
          setShowCTA(true);
          setTypingPhase('done');
        }, 300);
        return () => clearTimeout(timeout);
      }
    }
  }, [visibleBenefits, typingPhase]);

  // Blinking cursor
  useEffect(() => {
    const interval = setInterval(() => {
      setShowCursor(prev => !prev);
    }, 530);
    return () => clearInterval(interval);
  }, []);

  // ============================================================================
  // RETRY HANDLER
  // ============================================================================

  const handleRetryVerification = () => {
    setVerificationAttempts(0);
    setIsVerifying(true);
    setVerificationFailed(false);
  };

  // ============================================================================
  // RENDER: AUTH LOADING STATE
  // ============================================================================

  if (authLoading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
        <Loader2 className="h-8 w-8 animate-spin text-white/50" />
      </div>
    );
  }

  // ============================================================================
  // RENDER: LOADING/VERIFYING STATE
  // ============================================================================

  if (isVerifying) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
        <div className="text-center space-y-6">
          <Loader2 className="h-12 w-12 animate-spin text-white mx-auto" />
          <div>
            <h2 className="text-xl font-mono font-bold text-foreground">
              Confirming your upgrade...
            </h2>
            <p className="text-sm text-muted-foreground font-mono mt-2">
              Please wait while we verify your payment.
              {verificationAttempts > 0 && (
                <span className="block mt-1 text-xs">
                  Attempt {verificationAttempts + 1} of 5...
                </span>
              )}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ============================================================================
  // RENDER: VERIFICATION FAILED STATE
  // ============================================================================

  if (verificationFailed) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full space-y-6 text-center">
          <div className="mx-auto w-16 h-16 rounded-full bg-yellow-500/20 flex items-center justify-center">
            <AlertTriangle className="h-8 w-8 text-yellow-500" />
          </div>
          
          <div>
            <h2 className="text-xl font-mono font-bold text-foreground">
              Upgrade Processing
            </h2>
            <p className="text-sm text-muted-foreground font-mono mt-2">
              Your payment was received, but we&apos;re still processing your upgrade.
              This usually takes a few seconds but can occasionally take longer.
            </p>
          </div>
          
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
            <p className="text-sm text-yellow-200 font-mono">
              <strong>Don&apos;t worry!</strong> Your payment is secure. If your upgrade 
              doesn&apos;t appear within a few minutes, please contact support with your 
              payment confirmation email.
            </p>
          </div>
          
          <div className="space-y-3">
            <Button
              onClick={handleRetryVerification}
              className="w-full bg-yellow-500 text-black hover:bg-yellow-500/90 h-12 font-mono font-semibold"
            >
              <RefreshCw className="mr-2 h-5 w-5" />
              Check Again
            </Button>
            <Button
              onClick={() => router.push('/dashboard')}
              variant="outline"
              className="w-full font-mono"
            >
              Go to Dashboard
            </Button>
          </div>
          
          <p className="text-xs text-muted-foreground font-mono">
            Receipt: Check your email for payment confirmation.
          </p>
        </div>
      </div>
    );
  }

  // ============================================================================
  // RENDER: SUCCESS STATE WITH ANIMATION
  // ============================================================================

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
      {/* Background pattern - subtle grid (matching landing page) */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-background" />
        <div 
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
      </div>

      <div className="max-w-lg w-full space-y-8 text-center">
        {/* Animated Title */}
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight font-mono text-white">
          {typedTitle}
          <span 
            className={`text-white transition-opacity ${
              showCursor ? 'opacity-100' : 'opacity-0'
            }`}
          >
            _
          </span>
        </h1>

        {/* Animated Tagline */}
        <p className="text-xl sm:text-2xl text-white/80 font-bold font-mono tracking-wide min-h-[2em]">
          {typedTagline}
        </p>

        {/* Benefits Card */}
        <div 
          className={`
            bg-card/50 border border-border rounded-xl p-6 text-left
            transition-all duration-500
            ${typingPhase === 'benefits' || typingPhase === 'done' ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}
          `}
        >
          <h3 className="font-mono font-semibold text-white/60 mb-4 text-sm uppercase tracking-wider">
            What&apos;s unlocked:
          </h3>
          <ul className="space-y-3">
            {BENEFITS.map((benefit, index) => (
              <li 
                key={index}
                className={`
                  flex items-center gap-3 font-mono text-sm
                  transition-all duration-300
                  ${index < visibleBenefits ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-4'}
                `}
              >
                <Check className="h-5 w-5 text-white flex-shrink-0" />
                <span className="text-white/90">{benefit}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* CTA Buttons */}
        <div 
          className={`
            flex flex-col sm:flex-row gap-4 justify-center transition-all duration-500
            ${showCTA ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}
          `}
        >
          <Button
            onClick={() => router.push('/urls')}
            className="h-12 px-8 font-mono font-semibold text-base bg-white text-black hover:bg-white/90"
          >
            Explore URLs
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
          <Button
            onClick={() => router.push('/dashboard')}
            variant="outline"
            className="h-12 px-8 font-mono font-medium border-white/40 text-white hover:bg-white/10"
          >
            Dashboard
          </Button>
        </div>

        {/* Receipt Notice */}
        <p 
          className={`
            text-xs text-muted-foreground font-mono
            transition-all duration-500 delay-300
            ${showCTA ? 'opacity-100' : 'opacity-0'}
          `}
        >
          A receipt has been sent to your email.
        </p>
      </div>
    </div>
  );
}
