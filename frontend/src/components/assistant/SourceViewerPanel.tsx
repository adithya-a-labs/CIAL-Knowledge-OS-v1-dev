import { ChevronLeft, ChevronRight, FileSearch, X } from 'lucide-react';
import type { ChatSource } from '@/types/assistant';

interface SourceViewerPanelProps {
  open: boolean;
  source: ChatSource | null;
  sources: ChatSource[];
  onClose: () => void;
  onSelectSource: (source: ChatSource) => void;
}

function SourceTypeBadge({ sourceType }: { sourceType: ChatSource['sourceType'] }) {
  const label = sourceType === 'enterprise' ? 'Enterprise' : sourceType === 'workspace' ? 'Workspace' : 'Upload';
  const className =
    sourceType === 'enterprise'
      ? 'ce-badge-accent'
      : sourceType === 'workspace'
        ? 'bg-[#eef6fc] text-[#346c96] border-[#c7d8e8]'
        : 'bg-[#fff5e8] text-[#8a5208] border-[#efd8b5]';

  return (
    <span className={`ce-badge ${className}`}>
      {label}
    </span>
  );
}

function SourceViewerContent({
  source,
  sources,
  onClose,
  onSelectSource,
}: Omit<SourceViewerPanelProps, 'open'>) {
  const currentIndex = source ? sources.findIndex((candidate) => candidate.id === source.id) : -1;
  const previousSource = currentIndex > 0 ? sources[currentIndex - 1] : null;
  const nextSource = currentIndex >= 0 && currentIndex < sources.length - 1 ? sources[currentIndex + 1] : null;

  if (!source) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">Source Viewer</h2>
          <button type="button" onClick={onClose} className="ce-icon-button" data-testid="button-close-source-viewer-empty" aria-label="Close source viewer">
            <X size={16} />
          </button>
        </div>
        <div className="flex flex-1 items-center justify-center p-6">
          <div className="rounded-xl border border-dashed border-border bg-muted p-5 text-center">
            <FileSearch className="mx-auto mb-2 text-muted-foreground" size={28} />
            <p className="text-sm font-semibold text-foreground">No valid source selected</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Open a citation or source card to preview its mock document context.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col" data-testid="source-viewer-content">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="ce-badge ce-badge-accent">
                [{source.citationIndex}]
              </span>
              <SourceTypeBadge sourceType={source.sourceType} />
              {source.pageNumber && (
                <span className="ce-meta-text font-semibold">Page {source.pageNumber}</span>
              )}
            </div>
            <h2 className="safe-text text-sm font-semibold text-foreground">{source.documentTitle}</h2>
          </div>
          <button type="button" onClick={onClose} className="ce-icon-button" data-testid="button-close-source-viewer" aria-label="Close source viewer">
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="scrollbar-soft flex-1 overflow-y-auto p-4">
        <div className="flex min-h-[16rem] items-center justify-center rounded-xl border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
          <div className="w-full max-w-[18rem]">
            <FileSearch className="mx-auto mb-3 text-primary" size={34} />
            <p className="text-sm font-semibold text-foreground">Document preview placeholder</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Future integration: render documentId at pageNumber and highlight chunkId.
            </p>
            <div className="mt-4 space-y-1 rounded-lg border border-border bg-white p-3 text-left">
              <div className="h-2 w-5/6 rounded bg-muted" />
              <div className="h-2 w-full rounded bg-muted" />
              <div className="h-2 w-4/5 rounded bg-accent" />
              <div className="h-2 w-11/12 rounded bg-muted" />
            </div>
            <p className="mt-3 rounded-lg border border-border bg-white px-3 py-2 text-[11px] text-muted-foreground">
              {source.documentId} / page {source.pageNumber ?? 'n/a'} / {source.chunkId ?? 'chunk pending'}
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-border bg-white p-3">
          <p className="mb-2 text-xs font-semibold text-foreground">Highlighted excerpt</p>
          <p className="safe-text border-l-2 border-primary pl-3 text-sm leading-6 text-foreground">
            {source.excerpt ?? 'No excerpt available for this mock citation.'}
          </p>
        </div>

        {source.reason && (
          <div className="mt-3 rounded-xl border border-border bg-[hsl(210_20%_98%)] p-3">
            <p className="text-xs font-semibold text-muted-foreground">Why this source was used</p>
            <p className="safe-text mt-1 text-xs leading-5 text-foreground">{source.reason}</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 border-t border-border p-3">
        <button
          type="button"
          disabled={!previousSource}
          onClick={() => previousSource && onSelectSource(previousSource)}
          className="ce-action min-h-9 text-primary disabled:cursor-not-allowed disabled:opacity-40"
          data-testid="button-previous-citation"
        >
          <ChevronLeft size={14} />
          Previous
        </button>
        <button
          type="button"
          disabled={!nextSource}
          onClick={() => nextSource && onSelectSource(nextSource)}
          className="ce-action min-h-9 text-primary disabled:cursor-not-allowed disabled:opacity-40"
          data-testid="button-next-citation"
        >
          Next
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
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
      <aside className="ce-panel hidden w-[22rem] shrink-0 overflow-hidden lg:block 2xl:w-[26rem]" data-testid="source-viewer-panel">
        <SourceViewerContent
          source={source}
          sources={sources}
          onClose={onClose}
          onSelectSource={onSelectSource}
        />
      </aside>

      <div className="fixed inset-0 z-50 bg-black/45 lg:hidden" data-testid="source-viewer-mobile">
        <div className="ml-auto flex h-full w-full max-w-[32rem] flex-col border-l border-border bg-white shadow-2xl">
          <SourceViewerContent
            source={source}
            sources={sources}
            onClose={onClose}
            onSelectSource={onSelectSource}
          />
        </div>
      </div>
    </>
  );
}
