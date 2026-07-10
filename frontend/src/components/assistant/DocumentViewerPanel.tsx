import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileSearch } from 'lucide-react';
import { Link } from 'wouter';
import { getDocumentPreview } from '@/api/client';
import DocumentPreviewRenderer from './DocumentPreviewRenderer';
import DocumentToolbar from './DocumentToolbar';
import type { ChatSource } from '@/types/assistant';

interface DocumentViewerPanelProps {
  source: ChatSource | null;
  sources: ChatSource[];
  onClose: () => void;
  onSelectSource: (source: ChatSource) => void;
}

function excerptFor(source: ChatSource | null, previewText?: string | null) {
  return (
    source?.previewText
    || source?.highlightText
    || source?.excerpt
    || previewText
    || 'Open the full workspace to inspect the cited content.'
  );
}

function viewerSearchQuery(source: ChatSource | null, previewText?: string | null) {
  const candidate = source?.highlightText || source?.excerpt || previewText || '';
  return candidate.replace(/\s+/g, ' ').trim().slice(0, 120);
}

function SourceFallback({
  documentId,
  excerpt,
  pageNumber,
  sheetName,
  sheetIndex,
  slideNumber,
  anchor,
}: {
  documentId?: string | null;
  excerpt: string;
  pageNumber?: number | null;
  sheetName?: string | null;
  sheetIndex?: number | null;
  slideNumber?: number | null;
  anchor?: string | null;
}) {
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

  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-[#f7f9f6] px-6 py-8">
      <div className="w-full max-w-xl rounded-xl border border-[#dce4d8] bg-white p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[#eef5e8] text-primary">
            <FileSearch size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-slate-950">Exact inline navigation unavailable</h3>
            <p className="mt-1 text-xs leading-5 text-slate-600">
              The cited excerpt is still available below, and the full document workspace opens at the referenced location.
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Cited excerpt</p>
          <p className="safe-text mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{excerpt}</p>
        </div>

        {workspaceHref ? (
          <Link
            href={workspaceHref}
            className="mt-4 inline-flex h-9 items-center justify-center rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground transition hover:opacity-95"
          >
            Open Full Workspace
          </Link>
        ) : null}
      </div>
    </div>
  );
}

export default function DocumentViewerPanel({
  source,
  sources,
  onClose,
  onSelectSource,
}: DocumentViewerPanelProps) {
  const currentIndex = source ? sources.findIndex((candidate) => candidate.id === source.id) : -1;
  const previousSource = currentIndex > 0 ? sources[currentIndex - 1] : null;
  const nextSource = currentIndex >= 0 && currentIndex < sources.length - 1 ? sources[currentIndex + 1] : null;
  const [zoomLevel] = useState(1);
  const [activePage, setActivePage] = useState(1);
  const [requestedPage, setRequestedPage] = useState(1);
  const [pageCount, setPageCount] = useState<number | null>(null);

  useEffect(() => {
    const nextPage = source?.slideNumber ?? source?.pageNumber ?? 1;
    setActivePage(nextPage);
    setRequestedPage(nextPage);
    setPageCount(source?.pageCount ?? null);
  }, [source?.id, source?.pageCount, source?.pageNumber, source?.slideNumber]);

  const previewQuery = useQuery({
    queryKey: [
      'assistant-source-preview',
      source?.documentId,
      source?.chunkId ?? source?.anchor,
      source?.pageNumber,
      source?.sheetName,
      source?.sheetIndex,
      source?.slideNumber,
    ],
    queryFn: () =>
      getDocumentPreview(source!.documentId, {
        chunkId: source?.chunkId ?? source?.anchor,
        page: source?.pageNumber,
        sheetName: source?.sheetName,
        sheetIndex: source?.sheetIndex,
        slideNumber: source?.slideNumber,
      }),
    enabled: Boolean(source?.documentId),
    retry: false,
  });

  const preview = previewQuery.data ?? null;
  const title = preview?.name || source?.documentTitle || 'Source';
  const effectivePageNumber = source?.pageNumber ?? preview?.page ?? null;
  const effectiveSheetName = source?.sheetName ?? preview?.active_sheet ?? null;
  const effectiveSheetIndex = source?.sheetIndex ?? preview?.active_sheet_index ?? null;
  const effectiveSlideNumber = source?.slideNumber ?? preview?.active_slide_number ?? null;
  const searchQuery = useMemo(
    () => viewerSearchQuery(source, preview?.highlight_text || preview?.preview_text),
    [preview?.highlight_text, preview?.preview_text, source],
  );
  const fallbackExcerpt = excerptFor(source, preview?.preview_text);

  useEffect(() => {
    if (source?.slideNumber || source?.pageNumber) return;
    const previewPage = preview?.page;
    if (!previewPage || previewPage <= 0) return;
    setRequestedPage(previewPage);
    setActivePage(previewPage);
  }, [preview?.page, source?.pageNumber, source?.slideNumber]);

  if (!source) {
    return (
      <div className="flex h-full flex-col bg-white">
        <div className="flex min-h-0 flex-1 items-center justify-center px-6 py-8">
          <div className="rounded-xl border border-dashed border-[#dce4d8] bg-[#f7f9f6] px-6 py-8 text-center">
            <FileSearch className="mx-auto text-slate-400" size={30} />
            <p className="mt-3 text-sm font-semibold text-slate-900">No source selected</p>
          </div>
        </div>
      </div>
    );
  }

  const showRenderablePreview = Boolean(
    preview
    && (
      preview.viewer_ready
      || preview.render_kind !== 'card'
      || preview.preview_text
      || preview.rendered_html
    ),
  );
  const requiresExactPdfPage = preview?.render_kind === 'pdf';
  const hasExactPdfPage = !requiresExactPdfPage || Boolean(effectivePageNumber && effectivePageNumber > 0);
  const shouldRenderPreview = showRenderablePreview && hasExactPdfPage;

  return (
    <div className="flex h-full min-h-0 flex-col bg-white" data-testid="document-viewer-panel">
      <DocumentToolbar
        title={title}
        documentId={source.documentId}
        citationIndex={source.citationIndex}
        pageNumber={effectivePageNumber}
        sheetName={effectiveSheetName}
        sheetIndex={effectiveSheetIndex}
        slideNumber={effectiveSlideNumber}
        anchor={source.anchor ?? source.chunkId}
        currentIndex={Math.max(0, currentIndex)}
        total={sources.length}
        previousSource={previousSource}
        nextSource={nextSource}
        onPrevious={() => previousSource && onSelectSource(previousSource)}
        onNext={() => nextSource && onSelectSource(nextSource)}
        onClose={onClose}
      />

      <div className="min-h-0 flex-1 overflow-hidden bg-[#f7f9f6] p-3">
        {previewQuery.isLoading ? (
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-500">
            Loading source preview...
          </div>
        ) : shouldRenderPreview ? (
          <DocumentPreviewRenderer
            preview={preview}
            title={title}
            searchQuery={searchQuery}
            zoomLevel={zoomLevel}
            activePage={activePage}
            requestedPage={requestedPage}
            onPageCountChange={setPageCount}
            onActivePageChange={setActivePage}
            useNativePdf
          />
        ) : (
          <SourceFallback
            documentId={source.documentId}
            excerpt={fallbackExcerpt}
            pageNumber={effectivePageNumber}
            sheetName={effectiveSheetName}
            sheetIndex={effectiveSheetIndex}
            slideNumber={effectiveSlideNumber}
            anchor={source.anchor ?? source.chunkId}
          />
        )}
      </div>
    </div>
  );
}
