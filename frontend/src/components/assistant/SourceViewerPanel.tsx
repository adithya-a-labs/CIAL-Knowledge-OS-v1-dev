import { useEffect, useState } from 'react';
import DocumentViewerPanel from './DocumentViewerPanel';
import type { ChatSource } from '@/types/assistant';

interface SourceViewerPanelProps {
  open: boolean;
  source: ChatSource | null;
  sources: ChatSource[];
  onClose: () => void;
  onSelectSource: (source: ChatSource) => void;
}

export default function SourceViewerPanel({
  open,
  source,
  sources,
  onClose,
  onSelectSource,
}: SourceViewerPanelProps) {
  const [isDesktopViewport, setIsDesktopViewport] = useState(() => window.innerWidth >= 1024);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(min-width: 1024px)');
    const onChange = () => setIsDesktopViewport(mediaQuery.matches);
    onChange();
    mediaQuery.addEventListener('change', onChange);
    return () => mediaQuery.removeEventListener('change', onChange);
  }, []);

  if (!open) return null;

  if (isDesktopViewport) {
    return (
      <aside className="h-full min-h-0 w-full overflow-hidden bg-white" data-testid="source-viewer-panel">
        <DocumentViewerPanel source={source} sources={sources} onClose={onClose} onSelectSource={onSelectSource} />
      </aside>
    );
  }

  return (
    <div className="fixed inset-0 z-50" data-testid="source-viewer-mobile">
      <button className="absolute inset-0 bg-black/45" onClick={onClose} aria-label="Close source viewer overlay" />
      <div className="relative ml-auto flex h-full w-full max-w-[32rem] flex-col border-l border-border bg-white shadow-2xl">
        <DocumentViewerPanel source={source} sources={sources} onClose={onClose} onSelectSource={onSelectSource} />
      </div>
    </div>
  );
}
