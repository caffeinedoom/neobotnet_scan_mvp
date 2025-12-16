'use client';

/**
 * OAuth Callback Page
 * 
 * This page handles the redirect from Google/Twitter OAuth.
 * Supabase handles the token exchange automatically from the URL hash.
 * We listen for the auth state change to know when the session is ready.
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(true);

  useEffect(() => {
    // Listen for auth state changes - this is the reliable way to detect
    // when Supabase has processed the OAuth callback
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('Auth callback - state changed:', event, !!session);
        
        if (event === 'SIGNED_IN' && session) {
          console.log('Sign in confirmed, redirecting to dashboard...');
          // Small delay to ensure session is fully persisted
          setTimeout(() => {
            router.push('/dashboard');
          }, 100);
        } else if (event === 'SIGNED_OUT') {
          setError('Authentication was cancelled');
          setIsProcessing(false);
        }
      }
    );

    // Also check if we already have a session (in case the event already fired)
    const checkExistingSession = async () => {
      try {
        // Give Supabase time to process the URL hash
        await new Promise(resolve => setTimeout(resolve, 500));
        
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();

        if (sessionError) {
          console.error('Session error:', sessionError);
          setError(sessionError.message);
          setIsProcessing(false);
          return;
        }

        if (session) {
          console.log('Existing session found, redirecting...');
          router.push('/dashboard');
        } else {
          // No session after delay - might still be processing or failed
          // Wait a bit more then show error
          setTimeout(() => {
            setIsProcessing(false);
            setError('Authentication timed out. Please try again.');
          }, 5000);
        }
      } catch (err) {
        console.error('Callback error:', err);
        setError('An unexpected error occurred');
        setIsProcessing(false);
      }
    };

    checkExistingSession();

    return () => {
      subscription.unsubscribe();
    };
  }, [router]);

  if (error && !isProcessing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4 max-w-md p-6">
          <div className="text-destructive text-lg font-medium">
            Authentication Failed
          </div>
          <p className="text-muted-foreground">{error}</p>
          <button
            onClick={() => router.push('/auth/login')}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto" />
        <p className="text-muted-foreground">
          {isProcessing ? 'Completing sign in...' : 'Verifying authentication...'}
        </p>
      </div>
    </div>
  );
}

