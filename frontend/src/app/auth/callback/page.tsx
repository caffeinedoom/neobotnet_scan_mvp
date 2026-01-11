'use client';

/**
 * OAuth Callback Page
 * 
 * This page handles the redirect from Google/Twitter OAuth.
 * Supabase handles the token exchange automatically from the URL hash.
 * We listen for the auth state change to know when the session is ready.
 */

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabase';

// Inner component that uses useSearchParams (requires Suspense)
function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(true);
  const [debugInfo, setDebugInfo] = useState<string>('');

  useEffect(() => {
    // Debug: Log URL parameters and hash for OAuth debugging
    const urlHash = typeof window !== 'undefined' ? window.location.hash : '';
    const errorParam = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');
    const errorCode = searchParams.get('error_code');
    
    console.log('[OAuth Callback] Page loaded');
    console.log('[OAuth Callback] URL hash present:', !!urlHash);
    console.log('[OAuth Callback] URL hash length:', urlHash.length);
    console.log('[OAuth Callback] Error param:', errorParam);
    console.log('[OAuth Callback] Error description:', errorDescription);
    console.log('[OAuth Callback] Full URL:', typeof window !== 'undefined' ? window.location.href : 'N/A');
    
    // Check for OAuth errors in URL params (common with Twitter OAuth 2.0 failures)
    if (errorParam) {
      const fullError = `${errorParam}: ${errorDescription || 'Unknown error'}`;
      console.error('[OAuth Callback] OAuth error detected:', fullError);
      setError(fullError);
      setDebugInfo(`Error code: ${errorCode || 'N/A'}`);
      setIsProcessing(false);
      return;
    }

    // Listen for auth state changes - this is the reliable way to detect
    // when Supabase has processed the OAuth callback
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('[OAuth Callback] Auth state changed:', event, !!session);
        
        if (session) {
          console.log('[OAuth Callback] Session provider:', session.user?.app_metadata?.provider);
          console.log('[OAuth Callback] Session user ID:', session.user?.id);
        }
        
        if (event === 'SIGNED_IN' && session) {
          console.log('[OAuth Callback] Sign in confirmed, redirecting to dashboard...');
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
          console.error('[OAuth Callback] Session error:', sessionError);
          setError(sessionError.message);
          setDebugInfo(`Session error code: ${(sessionError as { code?: string })?.code || 'N/A'}`);
          setIsProcessing(false);
          return;
        }

        if (session) {
          console.log('[OAuth Callback] Existing session found, redirecting...');
          console.log('[OAuth Callback] Provider:', session.user?.app_metadata?.provider);
          router.push('/dashboard');
        } else {
          console.log('[OAuth Callback] No session found after initial check, waiting...');
          // No session after delay - might still be processing or failed
          // Wait a bit more then show error
          setTimeout(() => {
            setIsProcessing(false);
            // Check URL hash for any clues
            const hash = window.location.hash;
            if (hash && hash.includes('error')) {
              setError('OAuth provider returned an error. Check browser console for details.');
              setDebugInfo(`URL hash contains error. Hash length: ${hash.length}`);
            } else if (!hash) {
              setError('No authentication response received. The OAuth flow may have been interrupted.');
              setDebugInfo('No URL hash found - OAuth redirect may have failed');
            } else {
              setError('Authentication timed out. Please try again.');
              setDebugInfo(`Hash present but session not created. Hash length: ${hash.length}`);
            }
          }, 5000);
        }
      } catch (err) {
        console.error('[OAuth Callback] Callback error:', err);
        setError('An unexpected error occurred');
        setDebugInfo(err instanceof Error ? err.message : String(err));
        setIsProcessing(false);
      }
    };

    checkExistingSession();

    return () => {
      subscription.unsubscribe();
    };
  }, [router, searchParams]);

  if (error && !isProcessing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4 max-w-lg p-6">
          <div className="text-destructive text-lg font-medium">
            Authentication Failed
          </div>
          <p className="text-muted-foreground">{error}</p>
          {debugInfo && (
            <p className="text-xs text-muted-foreground font-mono bg-muted p-2 rounded">
              Debug: {debugInfo}
            </p>
          )}
          <div className="space-y-2">
            <button
              onClick={() => router.push('/auth/login')}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Try Again
            </button>
            <p className="text-xs text-muted-foreground">
              If this error persists, check the browser console (F12) for more details.
            </p>
          </div>
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

// Loading fallback for Suspense
function CallbackLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto" />
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}

// Main export with Suspense boundary
export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<CallbackLoading />}>
      <AuthCallbackContent />
    </Suspense>
  );
}
