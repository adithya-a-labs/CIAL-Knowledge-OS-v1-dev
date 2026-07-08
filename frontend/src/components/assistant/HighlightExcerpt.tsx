import { cn } from '@/lib/utils';

interface HighlightExcerptProps {
  text?: string | null;
  highlight?: string | null;
  className?: string;
}

export default function HighlightExcerpt({ text, highlight, className }: HighlightExcerptProps) {
  const value = (highlight || text || '').trim();
  if (!value) {
    return (
      <div className={cn('rounded-xl border border-dashed border-border bg-muted p-3 text-sm text-muted-foreground', className)}>
        No excerpt is available for this source.
      </div>
    );
  }

  return (
    <div className={cn('rounded-xl border border-[hsl(95_28%_78%)] bg-[hsl(95_24%_96%)] p-3', className)}>
      <p className="mb-2 text-xs font-semibold text-primary">Highlighted excerpt</p>
      <blockquote className="safe-text border-l-4 border-primary pl-3 text-sm leading-6 text-foreground">
        {value}
      </blockquote>
    </div>
  );
}

