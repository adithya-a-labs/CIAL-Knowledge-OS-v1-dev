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
  if (!open) return null;

  return (
    <>
      <aside className="ce-panel hidden h-full min-h-0 w-[22rem] shrink-0 overflow-hidden lg:block 2xl:w-[26rem]" data-testid="source-viewer-panel">
        <DocumentViewerPanel source={source} sources={sources} onClose={onClose} onSelectSource={onSelectSource} />
      </aside>

      <div className="fixed inset-0 z-50 bg-black/45 lg:hidden" data-testid="source-viewer-mobile">
        <div className="ml-auto flex h-full w-full max-w-[32rem] flex-col border-l border-border bg-white shadow-2xl">
          <DocumentViewerPanel source={source} sources={sources} onClose={onClose} onSelectSource={onSelectSource} />
        </div>
      </div>
    </>
  );
}

