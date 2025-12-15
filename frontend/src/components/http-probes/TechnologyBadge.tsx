import React from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface TechnologyBadgeProps {
  technology: string;
  className?: string;
  variant?: 'default' | 'outline';
}

/**
 * TechnologyBadge Component
 * 
 * Displays technology names with appropriate styling.
 * Uses outline variant for a clean, minimal look.
 */
export function TechnologyBadge({ 
  technology, 
  className,
  variant = 'outline' 
}: TechnologyBadgeProps) {
  return (
    <Badge
      variant={variant}
      className={cn(
        'text-xs font-normal',
        className
      )}
    >
      {technology}
    </Badge>
  );
}

interface TechnologyListProps {
  technologies: string[];
  limit?: number;
  className?: string;
  showCount?: boolean; // Show "+N more" when limited
}

/**
 * TechnologyList Component
 * 
 * Displays a list of technology badges with optional limit.
 * Shows "+N more" indicator when technologies exceed the limit.
 */
export function TechnologyList({ 
  technologies, 
  limit = 5,
  className,
  showCount = true 
}: TechnologyListProps) {
  if (!technologies || technologies.length === 0) {
    return (
      <span className="text-xs text-muted-foreground">No technologies detected</span>
    );
  }

  const displayTechnologies = limit ? technologies.slice(0, limit) : technologies;
  const remainingCount = technologies.length - displayTechnologies.length;

  return (
    <div className={cn('flex flex-wrap items-center gap-1.5', className)}>
      {displayTechnologies.map((tech, index) => (
        <TechnologyBadge key={`${tech}-${index}`} technology={tech} />
      ))}
      {showCount && remainingCount > 0 && (
        <Badge variant="secondary" className="text-xs font-normal">
          +{remainingCount} more
        </Badge>
      )}
    </div>
  );
}

/**
 * TechnologyCount Component
 * 
 * Displays technology name with count for statistics.
 */
interface TechnologyCountProps {
  name: string;
  count: number;
  className?: string;
}

export function TechnologyCountBadge({ 
  name, 
  count, 
  className 
}: TechnologyCountProps) {
  return (
    <div className={cn('flex items-center justify-between gap-2', className)}>
      <TechnologyBadge technology={name} />
      <span className="text-xs text-muted-foreground font-mono font-semibold">
        {count}
      </span>
    </div>
  );
}
