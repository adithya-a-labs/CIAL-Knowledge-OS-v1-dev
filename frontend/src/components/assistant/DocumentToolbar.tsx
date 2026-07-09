import { ChevronLeft, ChevronRight, Download, ExternalLink, FileText, Maximize2, RotateCcw, Search, ZoomIn, ZoomOut } from 'lucide-react';
import type { ChangeEvent } from 'react';
import { Link } from 'wouter';
import type { ChatSource } from '@/types/assistant';

interface DocumentToolbarProps {
  title: string;
  documentId?: string | null;
  citationIndex?: number;
  pageNumber?: number | null;
  pageCount?: number | null;
  pageLabel?: string;
  fileType?: string | null;
  currentIndex: number;
  total: number;
  previousSource: ChatSource | null;
  nextSource: ChatSource | null;
  searchValue: string;
  searchEnabled: boolean;
  zoomLevel: number;
  onPrevious: () => void;
  onNext: () => void;
  onClose: () => void;
  onSearchChange: (value: string) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  onPageChange: (value: number) => void;
  openUrl?: string | null;
  downloadUrl?: string | null;
}

export default function DocumentToolbar({
  title,
  documentId,
  citationIndex,
  pageNumber,
  pageCount,
  pageLabel = 'Page',
  fileType,
  currentIndex,
  total,
  previousSource,
  nextSource,
  searchValue,
  searchEnabled,
  zoomLevel,
  onPrevious,
  onNext,
  onClose,
  onSearchChange,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  onPageChange,
  openUrl,
  downloadUrl,
}: DocumentToolbarProps) {
  const handlePageChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextValue = Number(event.target.value);
    if (!Number.isFinite(nextValue) || nextValue < 1) return;
    onPageChange(nextValue);
  };

  return (
    <div className="sticky top-0 z-10 border-b border-border bg-white/95 px-5 py-4 backdrop-blur">
      <div className="min-w-0">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {citationIndex ? <span className="ce-badge ce-badge-accent">[{citationIndex}]</span> : null}
          {fileType ? <span className="ce-badge bg-[hsl(210_20%_98%)] text-muted-foreground">{fileType.toUpperCase()}</span> : null}
          <span className="ce-meta-text">{total > 0 ? `${currentIndex + 1} of ${total}` : 'Document'}</span>
        </div>
        <h2 className="safe-text flex min-w-0 items-center gap-2 text-base font-semibold text-foreground">
          <FileText size={18} className="shrink-0 text-primary" />
          <span className="truncate">{title}</span>
        </h2>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[13rem] flex-1">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
            disabled={!searchEnabled}
            placeholder={searchEnabled ? 'Search within preview' : 'Search unavailable'}
            className="h-10 w-full rounded-full border border-border bg-[hsl(210_20%_98%)] pl-9 pr-3 text-sm text-foreground outline-none transition focus:border-primary disabled:cursor-not-allowed disabled:opacity-55"
          />
        </div>

        <div className="flex items-center gap-1 rounded-full border border-border bg-[hsl(210_20%_98%)] p-1">
          <button type="button" onClick={onZoomOut} className="ce-icon-button h-8 w-8 rounded-full" aria-label="Zoom out">
            <ZoomOut size={14} />
          </button>
          <span className="min-w-12 text-center text-xs font-semibold text-muted-foreground">{Math.round(zoomLevel * 100)}%</span>
          <button type="button" onClick={onZoomReset} className="ce-icon-button h-8 w-8 rounded-full" aria-label="Reset zoom">
            <RotateCcw size={14} />
          </button>
          <button type="button" onClick={onZoomIn} className="ce-icon-button h-8 w-8 rounded-full" aria-label="Zoom in">
            <ZoomIn size={14} />
          </button>
        </div>

        <div className="flex items-center gap-2 rounded-full border border-border bg-[hsl(210_20%_98%)] px-3 py-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">{pageLabel}</span>
          <input
            type="number"
            min={1}
            max={pageCount ?? undefined}
            value={pageNumber ?? 1}
            onChange={handlePageChange}
            className="h-7 w-14 rounded-md border border-border bg-white px-2 text-sm text-foreground outline-none focus:border-primary"
          />
          {pageCount ? <span className="text-xs text-muted-foreground">/ {pageCount}</span> : null}
        </div>

        {documentId ? (
          <Link
            href={`/knowledge/document/${documentId}?page=${pageNumber ?? 1}`}
            className="ce-icon-button h-10 w-10 rounded-full flex items-center justify-center text-primary"
            title="Open full document"
            aria-label="Open full document"
          >
            <Maximize2 size={15} />
          </Link>
        ) : null}
        {openUrl ? (
          <a href={openUrl} target="_blank" rel="noreferrer" className="ce-icon-button h-10 w-10 rounded-full" aria-label="Open document">
            <ExternalLink size={15} />
          </a>
        ) : null}
        {downloadUrl ? (
          <a href={downloadUrl} className="ce-icon-button h-10 w-10 rounded-full" aria-label="Download document">
            <Download size={15} />
          </a>
        ) : null}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <button type="button" disabled={!previousSource} onClick={onPrevious} className="ce-action min-h-10 rounded-full text-primary disabled:opacity-40">
          <ChevronLeft size={14} />
          Previous
        </button>
        <button type="button" onClick={onClose} className="ce-action min-h-10 rounded-full text-muted-foreground">
          Close
        </button>
        <button type="button" disabled={!nextSource} onClick={onNext} className="ce-action min-h-10 rounded-full text-primary disabled:opacity-40">
          Next
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
