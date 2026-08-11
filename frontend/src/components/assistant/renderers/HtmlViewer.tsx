import { useEffect, useRef } from 'react';
import { zoomStyle } from './highlight-utils';
import { getReducedMotionPreference } from '@/hooks/useReducedMotionPreference';

interface HtmlViewerProps {
  html: string;
  zoomLevel: number;
}

export default function HtmlViewer({ html, zoomLevel }: HtmlViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    containerRef.current?.scrollTo({ top: 0, behavior: getReducedMotionPreference() ? 'auto' : 'smooth' });
  }, [html]);

  return (
    <div ref={containerRef} className="document-paper scrollbar-soft h-full overflow-auto rounded-[1.5rem] border border-border p-5">
      <iframe
        title="Sanitized document preview"
        className="h-full min-h-[32rem] w-full border-0"
        sandbox=""
        referrerPolicy="no-referrer"
        style={zoomStyle(zoomLevel)}
        srcDoc={`<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><body>${html}</body>`}
      />
    </div>
  );
}
