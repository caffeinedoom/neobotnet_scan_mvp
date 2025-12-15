import React from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface StatusCodeBadgeProps {
  statusCode: number | null;
  className?: string;
  showLabel?: boolean; // Show "Status:" prefix
}

/**
 * StatusCodeBadge Component
 * 
 * Displays HTTP status codes with appropriate color-coding:
 * - 2xx (Success): Green
 * - 3xx (Redirect): Blue
 * - 4xx (Client Error): Orange
 * - 5xx (Server Error): Red
 * - null/unknown: Gray
 */
export function StatusCodeBadge({ 
  statusCode, 
  className,
  showLabel = false 
}: StatusCodeBadgeProps) {
  // Determine color and variant based on status code
  const getStatusStyles = (code: number | null) => {
    if (!code) {
      return {
        variant: 'outline' as const,
        className: 'text-muted-foreground border-muted-foreground/30',
        label: 'Unknown',
      };
    }

    if (code >= 200 && code < 300) {
      return {
        variant: 'outline' as const,
        className: 'text-green-600 dark:text-green-400 border-green-600/30 dark:border-green-400/30 bg-green-50 dark:bg-green-950/20',
        label: String(code),
      };
    }

    if (code >= 300 && code < 400) {
      return {
        variant: 'outline' as const,
        className: 'text-blue-600 dark:text-blue-400 border-blue-600/30 dark:border-blue-400/30 bg-blue-50 dark:bg-blue-950/20',
        label: String(code),
      };
    }

    if (code >= 400 && code < 500) {
      return {
        variant: 'outline' as const,
        className: 'text-orange-600 dark:text-orange-400 border-orange-600/30 dark:border-orange-400/30 bg-orange-50 dark:bg-orange-950/20',
        label: String(code),
      };
    }

    if (code >= 500) {
      return {
        variant: 'destructive' as const,
        className: 'bg-red-50 dark:bg-red-950/20 text-red-600 dark:text-red-400 border-red-600/30',
        label: String(code),
      };
    }

    // Other status codes (1xx, etc.)
    return {
      variant: 'outline' as const,
      className: 'text-muted-foreground border-muted-foreground/30',
      label: String(code),
    };
  };

  const styles = getStatusStyles(statusCode);

  return (
    <Badge
      variant={styles.variant}
      className={cn(
        'font-mono font-semibold',
        styles.className,
        className
      )}
    >
      {showLabel && <span className="font-normal">Status: </span>}
      {styles.label}
    </Badge>
  );
}

/**
 * StatusCodeBadgeMini Component
 * 
 * Compact version without borders, suitable for inline display
 */
export function StatusCodeBadgeMini({ 
  statusCode, 
  className 
}: StatusCodeBadgeProps) {
  if (!statusCode) {
    return (
      <span className={cn('text-xs text-muted-foreground font-mono', className)}>
        —
      </span>
    );
  }

  const getTextColor = (code: number) => {
    if (code >= 200 && code < 300) return 'text-green-600 dark:text-green-400';
    if (code >= 300 && code < 400) return 'text-blue-600 dark:text-blue-400';
    if (code >= 400 && code < 500) return 'text-orange-600 dark:text-orange-400';
    if (code >= 500) return 'text-red-600 dark:text-red-400';
    return 'text-muted-foreground';
  };

  return (
    <span className={cn('text-xs font-mono font-semibold', getTextColor(statusCode), className)}>
      {statusCode}
    </span>
  );
}
