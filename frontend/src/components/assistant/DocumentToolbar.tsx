import { ChevronLeft, ChevronRight, Download, ExternalLink, FileText, X } from 'lucide-react';
import type { ChatSource } from '@/types/assistant';

interface DocumentToolbarProps {
  title: string;
  citationIndex?: number;
  pageNumber?: number;
  currentIndex: number;
  total: number;
  previousSource: ChatSource | null;
  nextSource: ChatSource | null;
  onPrevious: () => void;
  onNext: () => void;
  onClose: () => void;
  openUrl?: string | null;
  downloadUrl?: string | null;
}

export default function DocumentToolbar({
  title,
  citationIndex,
  pageNumber,
  currentIndex,
  total,
  previousSource,
  nextSource,
  onPrevious,
  onNext,
  onClose,
  openUrl,
  downloadUrl,
}: DocumentToolbarProps) {
  return (
    <div className="border-b border-border bg-white px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            {citationIndex ? <span className="ce-badge ce-badge-accent">[{citationIndex}]</span> : null}
            {pageNumber ? <span className="ce-badge bg-white text-muted-foreground">Page {pageNumber}</span> : null}
            <span className="ce-meta-text">{total > 0 ? `${currentIndex + 1} of ${total}` : 'Source'}</span>
          </div>
          <h2 className="safe-text flex min-w-0 items-center gap-2 text-sm font-semibold text-foreground">
            <FileText size={16} className="shrink-0 text-primary" />
            <span className="truncate">{title}</span>
          </h2>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {openUrl ? (
            <a href={openUrl} target="_blank" rel="noreferrer" className="ce-icon-button" aria-label="Open preview in new tab">
              <ExternalLink size={15} />
            </a>
          ) : null}
          {downloadUrl ? (
            <a href={downloadUrl} className="ce-icon-button" aria-label="Download document">
              <Download size={15} />
            </a>
          ) : null}
          <button type="button" onClick={onClose} className="ce-icon-button" aria-label="Close document viewer" data-testid="button-close-document-viewer">
            <X size={16} />
          </button>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button type="button" disabled={!previousSource} onClick={onPrevious} className="ce-action min-h-9 rounded-full text-primary disabled:opacity-40">
          <ChevronLeft size={14} />
          Previous
        </button>
        <button type="button" disabled={!nextSource} onClick={onNext} className="ce-action min-h-9 rounded-full text-primary disabled:opacity-40">
          Next
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
