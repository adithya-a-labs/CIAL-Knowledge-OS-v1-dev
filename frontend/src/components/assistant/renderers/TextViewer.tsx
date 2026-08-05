import { useEffect, useMemo, useRef } from 'react';
import { highlightHtml, zoomStyle } from './highlight-utils';
import { getReducedMotionPreference } from '@/hooks/useReducedMotionPreference';

interface TextViewerProps {
  text: string;
  searchQuery: string;
  zoomLevel: number;
  code?: boolean;
}

export default function TextViewer({ text, searchQuery, zoomLevel, code = false }: TextViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const highlightedText = useMemo(() => highlightHtml(text, searchQuery), [searchQuery, text]);

  useEffect(() => {
    const firstHit = containerRef.current?.querySelector('[data-search-hit="true"]');
    if (firstHit instanceof HTMLElement) {
      firstHit.scrollIntoView({ behavior: getReducedMotionPreference() ? 'auto' : 'smooth', block: 'center' });
    }
  }, [highlightedText]);

  return (
    <div
      ref={containerRef}
      className={`scrollbar-soft h-full overflow-auto rounded-[1.5rem] border border-border ${code ? 'bg-muted p-4' : 'bg-card p-5'}`}
    >
      {code ? (
        <pre
          className="text-xs leading-6 text-foreground"
          style={zoomStyle(zoomLevel)}
          dangerouslySetInnerHTML={{ __html: highlightedText }}
        />
      ) : (
        <div
          className="safe-text whitespace-pre-wrap text-sm leading-7 text-foreground"
          style={zoomStyle(zoomLevel)}
          dangerouslySetInnerHTML={{ __html: highlightedText }}
        />
      )}
    </div>
  );
}
