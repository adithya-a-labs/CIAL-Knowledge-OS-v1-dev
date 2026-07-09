import { useEffect, useRef } from 'react';
import { zoomStyle } from './highlight-utils';

interface HtmlViewerProps {
  html: string;
  zoomLevel: number;
}

export default function HtmlViewer({ html, zoomLevel }: HtmlViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    containerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [html]);

  return (
    <div ref={containerRef} className="scrollbar-soft h-full overflow-auto rounded-[1.5rem] border border-border bg-white p-5">
      <article
        className="prose prose-slate max-w-none"
        style={zoomStyle(zoomLevel)}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
