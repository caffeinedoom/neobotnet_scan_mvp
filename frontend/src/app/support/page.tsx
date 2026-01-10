'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

export default function SupportPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  // Redirect unauthenticated users to landing page
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, router]);

  // Load Youform embed script - force re-initialization on SPA navigation
  useEffect(() => {
    // Remove any existing youform script to force re-initialization
    const existingScript = document.querySelector('script[src="https://app.youform.com/embed.js"]');
    if (existingScript) {
      existingScript.remove();
    }

    // Small delay to ensure DOM is ready after navigation
    const timer = setTimeout(() => {
      const script = document.createElement('script');
      script.src = 'https://app.youform.com/embed.js';
      script.async = true;
      document.body.appendChild(script);
    }, 100);

    return () => {
      clearTimeout(timer);
      const script = document.querySelector('script[src="https://app.youform.com/embed.js"]');
      if (script) {
        script.remove();
      }
    };
  }, []);

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="max-w-2xl mx-auto space-y-6">
          <div className="h-8 bg-muted animate-pulse rounded w-32" />
          <div className="h-4 bg-muted animate-pulse rounded w-64" />
          <div className="h-[700px] bg-muted animate-pulse rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-2xl mx-auto space-y-6">
        
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Support</h1>
          <p className="text-muted-foreground mt-1">
            We&apos;re here to help. Drop us a message.
          </p>
        </div>

        {/* Youform Embed */}
        <div className="rounded-lg border border-border/50 bg-card/30 overflow-hidden">
          <div 
            data-youform-embed 
            data-form="zdrwes6n"
            data-width="100%" 
            data-height="700"
          />
        </div>

      </div>
    </div>
  );
}
