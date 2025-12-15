import React from 'react';
import { ArrowRight, ExternalLink } from 'lucide-react';
import { StatusCodeBadgeMini } from './StatusCodeBadge';
import { cn } from '@/lib/utils';

interface RedirectChainVisualizerProps {
  chainStatusCodes: number[];
  url: string;
  finalUrl?: string | null;
  className?: string;
  compact?: boolean; // Compact mode for table display
}

/**
 * RedirectChainVisualizer Component
 * 
 * Visualizes HTTP redirect chains with status codes.
 * Example: 302 → 302 → 200
 */
export function RedirectChainVisualizer({
  chainStatusCodes,
  url,
  finalUrl,
  className,
  compact = false,
}: RedirectChainVisualizerProps) {
  const hasRedirects = chainStatusCodes && chainStatusCodes.length > 0;

  if (!hasRedirects) {
    return (
      <span className={cn('text-xs text-muted-foreground', className)}>
        No redirects
      </span>
    );
  }

  if (compact) {
    return (
      <div className={cn('flex items-center gap-1 flex-wrap', className)}>
        {chainStatusCodes.map((code, index) => (
          <React.Fragment key={index}>
            <StatusCodeBadgeMini statusCode={code} />
            {index < chainStatusCodes.length - 1 && (
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
            )}
          </React.Fragment>
        ))}
      </div>
    );
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-semibold">Redirect Chain:</span>
        <span className="font-mono">
          {chainStatusCodes.length} step{chainStatusCodes.length > 1 ? 's' : ''}
        </span>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {chainStatusCodes.map((code, index) => (
          <React.Fragment key={index}>
            <div className="flex items-center gap-1.5">
              <StatusCodeBadgeMini statusCode={code} />
              <span className="text-xs text-muted-foreground">
                {index === 0 && 'Start'}
                {index === chainStatusCodes.length - 1 && 'Final'}
              </span>
            </div>
            {index < chainStatusCodes.length - 1 && (
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            )}
          </React.Fragment>
        ))}
      </div>

      {finalUrl && finalUrl !== url && (
        <div className="mt-3 p-2 bg-muted/50 rounded-md">
          <div className="flex items-start gap-2">
            <ExternalLink className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground font-semibold">Final URL:</p>
              <code className="text-xs font-mono break-all text-foreground">
                {finalUrl}
              </code>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * RedirectChainIndicator Component
 * 
 * Simple indicator showing redirect count (for table cells)
 */
interface RedirectChainIndicatorProps {
  chainStatusCodes: number[];
  className?: string;
}

export function RedirectChainIndicator({
  chainStatusCodes,
  className,
}: RedirectChainIndicatorProps) {
  const hasRedirects = chainStatusCodes && chainStatusCodes.length > 0;

  if (!hasRedirects) {
    return (
      <span className={cn('text-xs text-muted-foreground', className)}>—</span>
    );
  }

  return (
    <div className={cn('flex items-center gap-1', className)}>
      <ArrowRight className="h-3 w-3 text-blue-600 dark:text-blue-400" />
      <span className="text-xs font-mono font-semibold text-blue-600 dark:text-blue-400">
        {chainStatusCodes.length}
      </span>
    </div>
  );
}
