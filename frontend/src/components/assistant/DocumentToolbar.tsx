import { ChevronLeft, ChevronRight, FileText, X } from 'lucide-react';
import { Link } from 'wouter';
import type { ChatSource } from '@/types/assistant';

interface DocumentToolbarProps {
  title: string;
  documentId?: string | null;
  citationIndex?: number;
  pageNumber?: number | null;
  sheetName?: string | null;
  sheetIndex?: number | null;
  slideNumber?: number | null;
  anchor?: string | null;
  currentIndex: number;
  total: number;
  previousSource: ChatSource | null;
  nextSource: ChatSource | null;
  onPrevious: () => void;
  onNext: () => void;
  onClose: () => void;
}

export default function DocumentToolbar({
  title,
  documentId,
  citationIndex,
  pageNumber,
  sheetName,
  sheetIndex,
  slideNumber,
  anchor,
  currentIndex,
  total,
  previousSource,
  nextSource,
  onPrevious,
  onNext,
  onClose,
}: DocumentToolbarProps) {
  const workspaceHref = (() => {
    if (!documentId) return null;
    const params = new URLSearchParams();
    if (pageNumber) params.set('page', String(pageNumber));
    if (slideNumber) params.set('slide', String(slideNumber));
    if (sheetName) params.set('sheet', sheetName);
    if (sheetIndex) params.set('sheetIndex', String(sheetIndex));
    if (anchor) params.set('chunk', anchor);
    const query = params.toString();
    return `/knowledge/document/${documentId}${query ? `?${query}` : ''}`;
  })();
  const locationLabel = sheetName
    ? `Sheet ${sheetName}${sheetIndex ? ` (${sheetIndex})` : ''}`
    : slideNumber
      ? `Slide ${slideNumber}`
      : pageNumber
        ? `Page ${pageNumber}`
        : 'Location unavailable';

  return (
    <div className="sticky top-0 z-10 border-b border-[#e3e9e1] bg-white/95 px-4 py-3 backdrop-blur">
      <div className="flex min-w-0 items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
            {citationIndex ? (
              <span className="rounded-md bg-[#eef5e8] px-1.5 py-0.5 font-semibold text-primary">[{citationIndex}]</span>
            ) : null}
            <span className="font-medium">{locationLabel}</span>
            <span>{total > 0 ? `${currentIndex + 1} of ${total}` : 'Citation'}</span>
          </div>
          <div className="flex min-w-0 items-center gap-2">
            <FileText size={16} className="shrink-0 text-primary" />
            <h2 className="truncate text-sm font-semibold text-slate-950">{title}</h2>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            disabled={!previousSource}
            onClick={onPrevious}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#dce4d8] bg-white text-slate-600 transition hover:bg-[#f6f8f5] hover:text-slate-950 disabled:opacity-40"
            aria-label="Previous citation"
            title="Previous citation"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            disabled={!nextSource}
            onClick={onNext}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#dce4d8] bg-white text-slate-600 transition hover:bg-[#f6f8f5] hover:text-slate-950 disabled:opacity-40"
            aria-label="Next citation"
            title="Next citation"
          >
            <ChevronRight size={14} />
          </button>
          {workspaceHref ? (
            <Link
              href={workspaceHref}
              className="inline-flex h-8 items-center justify-center rounded-md border border-[#dce4d8] bg-[#f7faf5] px-2.5 text-xs font-medium text-primary transition hover:bg-[#eef5e8]"
            >
              Open Full Workspace
            </Link>
          ) : null}
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#dce4d8] bg-white text-slate-600 transition hover:bg-[#f6f8f5] hover:text-slate-950"
            aria-label="Close source drawer"
            title="Close"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
