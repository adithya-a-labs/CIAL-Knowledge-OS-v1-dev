import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileSearch } from 'lucide-react';
import { Link } from 'wouter';
import { getDocumentPreview } from '@/api/client';
import type { DocumentPreview } from '@/api/types';
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

function normalizedPage(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return null;
  return Math.trunc(value);
}

function resolvedPageNumber(source: ChatSource | null, preview?: DocumentPreview | null) {
  const explicit = normalizedPage(source?.pageNumber ?? preview?.page ?? null);
  if (explicit !== null) return explicit;
  const pageIndex = source?.pageIndex;
  return typeof pageIndex === 'number' && Number.isFinite(pageIndex) && pageIndex >= 0
    ? Math.trunc(pageIndex) + 1
    : null;
}

function isPdfSource(source: ChatSource | null, preview: DocumentPreview | null) {
  const fileType = (source?.fileType || '').replace(/^\./, '').toLowerCase();
  const title = (source?.documentTitle || source?.relativePath || '').toLowerCase();
  const previewFormat = (preview?.viewer_format || '').replace(/^\./, '').toLowerCase();
  return (
    fileType === 'pdf'
    || title.endsWith('.pdf')
    || preview?.render_kind === 'pdf'
    || previewFormat === 'pdf'
  );
}

function pdfPreviewFromSource(source: ChatSource, pageNumber: number, preview: DocumentPreview | null): DocumentPreview | null {
  const fileUrl = preview?.file_url || source.fileUrl;
  const documentId = preview?.document_id || source.documentId;
  if (!fileUrl || !documentId) return null;
  return {
    ...(preview ?? {
      id: documentId,
      folder_id: null,
      name: source.documentTitle,
      relative_path: source.relativePath || '',
      extension: '.pdf',
      mime_type: 'application/pdf',
      file_type: 'pdf',
      size_bytes: 0,
      content_hash: null,
      modified_at: null,
      indexed: true,
      indexing_status: 'indexed',
      indexed_at: null,
      page_count: source.pageCount ?? null,
      created_at: '',
      updated_at: '',
      preview_text: source.previewText || source.excerpt || '',
      highlight_text: source.highlightText || source.previewText || source.excerpt || '',
      page: pageNumber,
      chunk_id: source.chunkId ?? source.anchor ?? null,
      open_url: null,
      download_url: null,
      read_error: null,
    }),
    document_id: documentId,
    file_url: fileUrl,
    viewer_url: fileUrl,
    viewer_format: 'pdf',
    viewer_ready: true,
    render_kind: 'pdf',
    page: pageNumber,
    page_count: preview?.page_count ?? source.pageCount ?? null,
    chunk_id: preview?.chunk_id ?? source.chunkId ?? source.anchor ?? null,
    preview_text: preview?.preview_text ?? source.previewText ?? source.excerpt ?? '',
    highlight_text: preview?.highlight_text ?? source.highlightText ?? source.previewText ?? source.excerpt ?? '',
  };
}

function logCitationNavigation(
  source: ChatSource | null,
  values: {
    extractedPage: number | null;
    normalizedPage: number | null;
    pdfEndpointUrl?: string | null;
    viewerUrl?: string | null;
    fallbackReason?: string | null;
  },
) {
  if (typeof console === 'undefined') return;
  console.debug('[citation-pdf-navigation]', {
    citationId: source?.citationId ?? source?.id ?? null,
    documentId: source?.documentId ?? null,
    repositoryId: source?.repositoryId ?? null,
    extractedPage: values.extractedPage,
    normalizedPage: values.normalizedPage,
    pdfEndpointUrl: values.pdfEndpointUrl ?? source?.fileUrl ?? null,
    viewerUrl: values.viewerUrl ?? null,
    fallbackReason: values.fallbackReason ?? null,
  });
}

function SourceFallback({
  documentId,
  citationId,
  excerpt,
  pageNumber,
  sheetName,
  sheetIndex,
  slideNumber,
  anchor,
  reason,
}: {
  documentId?: string | null;
  citationId?: string | null;
  excerpt: string;
  pageNumber?: number | null;
  sheetName?: string | null;
  sheetIndex?: number | null;
  slideNumber?: number | null;
  anchor?: string | null;
  reason: string;
}) {
  const workspaceHref = (() => {
    if (!documentId) return null;
    const params = new URLSearchParams();
    if (pageNumber !== null && pageNumber !== undefined && pageNumber > 0) params.set('page', String(pageNumber));
    if (citationId) params.set('citation', citationId);
    if (slideNumber) params.set('slide', String(slideNumber));
    if (sheetName) params.set('sheet', sheetName);
    if (sheetIndex) params.set('sheetIndex', String(sheetIndex));
    if (anchor && !citationId) params.set('chunk', anchor);
    const query = params.toString();
    return `/knowledge/document/${documentId}${query ? `?${query}` : ''}`;
  })();

  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-muted px-6 py-8">
      <div className="w-full max-w-xl rounded-xl border border-border bg-card p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent text-primary">
            <FileSearch size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-foreground">Source preview unavailable</h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              {reason}
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-border bg-muted px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Cited excerpt</p>
          <p className="safe-text mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">{excerpt}</p>
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
    const nextPage = source?.slideNumber ?? resolvedPageNumber(source) ?? 1;
    setActivePage(nextPage);
    setRequestedPage(nextPage);
    setPageCount(source?.pageCount ?? null);
  }, [source?.id, source?.pageCount, source?.pageNumber, source?.pageIndex, source?.slideNumber]);

  const previewQuery = useQuery({
    queryKey: [
      'assistant-source-preview',
      source?.documentId,
      source?.chunkId ?? source?.anchor,
      source?.pageNumber,
      source?.pageIndex,
      source?.sheetName,
      source?.sheetIndex,
      source?.slideNumber,
    ],
    queryFn: () =>
      getDocumentPreview(source!.documentId, {
        chunkId: source?.chunkId ?? source?.anchor,
        page: resolvedPageNumber(source) ?? undefined,
        sheetName: source?.sheetName,
        sheetIndex: source?.sheetIndex,
        slideNumber: source?.slideNumber,
      }),
    enabled: Boolean(source?.documentId),
    retry: false,
  });

  const preview = previewQuery.data ?? null;
  const title = preview?.name || source?.documentTitle || 'Source';
  const extractedPageNumber = source?.pageNumber ?? preview?.page ?? null;
  const effectivePageNumber = resolvedPageNumber(source, preview);
  const effectiveSheetName = source?.sheetName ?? preview?.active_sheet ?? null;
  const effectiveSheetIndex = source?.sheetIndex ?? preview?.active_sheet_index ?? null;
  const effectiveSlideNumber = source?.slideNumber ?? preview?.active_slide_number ?? null;
  const searchQuery = useMemo(
    () => viewerSearchQuery(source, preview?.highlight_text || preview?.preview_text),
    [preview?.highlight_text, preview?.preview_text, source],
  );
  const fallbackExcerpt = excerptFor(source, preview?.preview_text);
  const sourceIsPdf = isPdfSource(source, preview);
  const pdfPreview = source && sourceIsPdf && effectivePageNumber && !previewQuery.isError
    ? pdfPreviewFromSource(source, effectivePageNumber, preview)
    : null;
  const previewForRenderer = pdfPreview ?? preview;
  const pdfViewerUrl = pdfPreview?.viewer_url && effectivePageNumber
    ? `${pdfPreview.viewer_url}#page=${effectivePageNumber}`
    : null;
  const fallbackReason = (() => {
    if (sourceIsPdf && !effectivePageNumber) return 'Page metadata is missing for this PDF citation.';
    if (sourceIsPdf && !source?.fileUrl && !preview?.file_url) return 'The PDF file endpoint was not provided for this citation.';
    if (previewQuery.isError) return 'The PDF request failed or access was denied for this document.';
    return 'This source is not page-addressable in the inline viewer.';
  })();

  useEffect(() => {
    if (source?.slideNumber || resolvedPageNumber(source) !== null) return;
    const previewPage = preview?.page;
    if (!previewPage || previewPage <= 0) return;
    setRequestedPage(previewPage);
    setActivePage(previewPage);
  }, [preview?.page, source, source?.pageNumber, source?.pageIndex, source?.slideNumber]);

  useEffect(() => {
    logCitationNavigation(source, {
      extractedPage: normalizedPage(extractedPageNumber),
      normalizedPage: effectivePageNumber,
      pdfEndpointUrl: pdfPreview?.viewer_url ?? preview?.file_url ?? source?.fileUrl ?? null,
      viewerUrl: pdfViewerUrl,
      fallbackReason: pdfPreview ? null : fallbackReason,
    });
  }, [effectivePageNumber, extractedPageNumber, fallbackReason, pdfPreview, pdfViewerUrl, preview?.file_url, source]);

  if (!source) {
    return (
      <div className="flex h-full flex-col bg-card">
        <div className="flex min-h-0 flex-1 items-center justify-center px-6 py-8">
          <div className="rounded-xl border border-dashed border-border bg-muted px-6 py-8 text-center">
            <FileSearch className="mx-auto text-muted-foreground" size={30} />
            <p className="mt-3 text-sm font-semibold text-foreground">No source selected</p>
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
    <div className="flex h-full min-h-0 flex-col bg-card" data-testid="document-viewer-panel">
      <DocumentToolbar
        title={title}
        documentId={source.documentId}
        citationIndex={source.citationIndex}
        pageNumber={effectivePageNumber}
        sheetName={effectiveSheetName}
        sheetIndex={effectiveSheetIndex}
        slideNumber={effectiveSlideNumber}
        anchor={source.anchor ?? source.chunkId}
        citationId={source.citationId ?? source.id}
        currentIndex={Math.max(0, currentIndex)}
        total={sources.length}
        previousSource={previousSource}
        nextSource={nextSource}
        onPrevious={() => previousSource && onSelectSource(previousSource)}
        onNext={() => nextSource && onSelectSource(nextSource)}
        onClose={onClose}
      />

      <div className="min-h-0 flex-1 overflow-hidden bg-muted p-3">
        {previewQuery.isLoading ? (
          <div className="flex h-full items-center justify-center px-6 text-sm text-muted-foreground">
            Loading source preview...
          </div>
        ) : shouldRenderPreview || pdfPreview ? (
          <DocumentPreviewRenderer
            preview={previewForRenderer}
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
            citationId={source.citationId ?? source.id}
            excerpt={fallbackExcerpt}
            pageNumber={effectivePageNumber}
            sheetName={effectiveSheetName}
            sheetIndex={effectiveSheetIndex}
            slideNumber={effectiveSlideNumber}
            anchor={source.anchor ?? source.chunkId}
            reason={fallbackReason}
          />
        )}
      </div>
    </div>
  );
}
