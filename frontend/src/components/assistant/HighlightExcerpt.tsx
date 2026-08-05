import { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { getReducedMotionPreference } from '@/hooks/useReducedMotionPreference';

interface HighlightExcerptProps {
  text?: string | null;
  highlight?: string | null;
  className?: string;
}

export default function HighlightExcerpt({ text, highlight, className }: HighlightExcerptProps) {
  const value = (highlight || text || '').trim();
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!value) return;
    containerRef.current?.scrollIntoView({
      behavior: getReducedMotionPreference() ? 'auto' : 'smooth',
      block: 'nearest',
    });
  }, [value]);

  if (!value) {
    return (
      <div className={cn('rounded-xl border border-dashed border-border bg-muted p-3 text-sm text-muted-foreground', className)}>
        No excerpt is available for this source.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        'rounded-xl border border-primary/25 bg-primary/5 p-3 shadow-[0_0_0_0_rgba(74,124,63,0)] transition-shadow duration-[var(--motion-duration-standard)] ease-[var(--motion-ease-enter)] motion-reduce:transition-none data-[active=true]:shadow-[0_0_0_4px_rgba(74,124,63,0.16)]',
        className,
      )}
      data-active="true"
    >
      <p className="mb-2 text-xs font-semibold text-primary">Highlighted excerpt</p>
      <blockquote className="safe-text border-l-4 border-primary pl-3 text-sm leading-6 text-foreground">
        {value}
      </blockquote>
    </div>
  );
}
