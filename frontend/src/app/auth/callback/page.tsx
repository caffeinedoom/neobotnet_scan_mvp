'use client';

/**
 * OAuth Callback Page
 * 
 * This page handles the redirect from Google OAuth.
 * Supabase handles the token exchange automatically.
 * We just need to detect the session and redirect to the main app.
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Supabase automatically handles the OAuth callback
        // and sets the session from the URL hash/params
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();

        if (sessionError) {
          console.error('Session error:', sessionError);
          setError(sessionError.message);
          return;
        }

        if (session) {
          console.log('Authentication successful, redirecting...');
          // Redirect to the programs page (main app)
          router.push('/programs');
        } else {
          // No session yet, might still be processing
          // Wait a bit and check again
          setTimeout(async () => {
            const { data: { session: retrySession } } = await supabase.auth.getSession();
            if (retrySession) {
              router.push('/programs');
            } else {
              setError('Authentication failed. Please try again.');
            }
          }, 1000);
        }
      } catch (err) {
        console.error('Callback error:', err);
        setError('An unexpected error occurred');
      }
    };

    handleCallback();
  }, [router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
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
          Completing sign in...
        </p>
      </div>
    </div>
  );
}

