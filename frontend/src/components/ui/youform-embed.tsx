'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

interface YouFormEmbedProps {
  /** YouForm form ID (e.g., 'w99tz8px') */
  formId: string;
  /** Height of the embed in pixels */
  height?: number;
  /** Additional className for the container */
  className?: string;
  /** Title for accessibility (iframe title attribute) */
  title?: string;
}

/**
 * YouFormEmbed Component
 * 
 * Embeds a YouForm form using a direct iframe approach.
 * This method is SPA-friendly and works reliably with client-side navigation
 * in Next.js, unlike the script-based embed which has lifecycle issues.
 * 
 * @example
 * ```tsx
 * <YouFormEmbed formId="w99tz8px" height={600} />
 * ```
 */
export function YouFormEmbed({ 
  formId, 
  height = 600,
  className,
  title = 'YouForm Embed'
}: YouFormEmbedProps) {
  const [isLoading, setIsLoading] = useState(true);

  const formUrl = `https://app.youform.com/forms/${formId}`;

  return (
    <div 
      data-slot="youform-embed"
      className={cn(
        'relative w-full overflow-hidden rounded-lg',
        className
      )}
      style={{ height: `${height}px` }}
    >
      {/* Loading state - shown until iframe loads */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/50 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Loading form...</span>
          </div>
        </div>
      )}

      {/* iframe - always rendered, loading indicator shown on top */}
      <iframe
        src={formUrl}
        width="100%"
        height="100%"
        style={{ 
          border: 'none',
          opacity: isLoading ? 0 : 1,
          transition: 'opacity 0.2s ease-in-out'
        }}
        title={title}
        loading="lazy"
        onLoad={() => setIsLoading(false)}
        allow="clipboard-write"
      />
    </div>
  );
}
