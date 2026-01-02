'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckCircle2, ArrowRight, Sparkles, Loader2 } from 'lucide-react';
import confetti from 'canvas-confetti';

export default function UpgradeSuccessPage() {
  const router = useRouter();
  const [showContent, setShowContent] = useState(false);

  useEffect(() => {
    // Trigger confetti celebration
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

    // Show content after a brief delay
    setTimeout(() => setShowContent(true), 500);

    return () => clearInterval(interval);
  }, []);

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
