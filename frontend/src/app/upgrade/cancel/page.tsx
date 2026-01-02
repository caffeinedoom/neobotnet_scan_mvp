'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { XCircle, ArrowLeft, RefreshCw } from 'lucide-react';

export default function UpgradeCancelPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="max-w-md w-full border-border/50 bg-card/50">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
            <XCircle className="h-8 w-8 text-muted-foreground" />
          </div>
          <CardTitle className="text-xl">Payment Cancelled</CardTitle>
          <CardDescription className="text-base mt-2">
            No worries! Your payment was cancelled and you haven&apos;t been charged.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <Button
              onClick={() => router.push('/upgrade')}
              className="w-full bg-[--terminal-green] text-black hover:bg-[--terminal-green]/90"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Try Again
            </Button>
            <Button
              onClick={() => router.push('/urls')}
              variant="outline"
              className="w-full"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Continue with Free Tier
            </Button>
          </div>

          <p className="text-xs text-center text-muted-foreground pt-2">
            Questions? Contact us at support@neobotnet.com
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
