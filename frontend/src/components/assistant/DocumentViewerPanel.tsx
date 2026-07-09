import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, FileSearch, Sparkles } from 'lucide-react';
import { Link } from 'wouter';
import { apiUrl, getDocumentPreview } from '@/api/client';
import DocumentToolbar from './DocumentToolbar';
import HighlightExcerpt from './HighlightExcerpt';
import type { ChatSource } from '@/types/assistant';

interface DocumentViewerPanelProps {
  source: ChatSource | null;
  sources: ChatSource[];
  onClose: () => void;
  onSelectSource: (source: ChatSource) => void;
}

function formatBytes(value?: number | null) {
  if (!value) return 'Unknown size';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function looksLikeUuid(value?: string) {
  return Boolean(value && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value));
}

export default function DocumentViewerPanel({
  source,
  sources,
  onClose,
  onSelectSource,
}: DocumentViewerPanelProps) {
  const [activeDocument, setActiveDocument] = useState<string | null>(source?.documentId ?? null);
  const [activePage, setActivePage] = useState<number | null>(source?.pageNumber ?? null);
  const [previewPage, setPreviewPage] = useState<number | null>(source?.pageNumber ?? null);
  const [activeChunk, setActiveChunk] = useState<string | null>(source?.chunkId ?? null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [pageCount, setPageCount] = useState<number | null>(source?.pageCount ?? null);

  useEffect(() => {
    setActiveDocument(source?.documentId ?? null);
    setActivePage(source?.pageNumber ?? null);
    setPreviewPage(source?.pageNumber ?? null);
    setActiveChunk(source?.chunkId ?? null);
    setZoomLevel(1);
    setSearchQuery('');
    setPageCount(source?.pageCount ?? null);
  }, [source?.documentId, source?.pageNumber, source?.chunkId, source?.id]);

  const currentIndex = source ? sources.findIndex((candidate) => candidate.id === source.id) : -1;
  const previousSource = currentIndex > 0 ? sources[currentIndex - 1] : null;
  const nextSource = currentIndex >= 0 && currentIndex < sources.length - 1 ? sources[currentIndex + 1] : null;
  const canFetchPreview = looksLikeUuid(activeDocument ?? undefined);

  const previewQuery = useQuery({
    queryKey: ['document-preview', activeDocument, activeChunk, previewPage],
    queryFn: () => getDocumentPreview(activeDocument!, activeChunk ?? undefined, previewPage ?? undefined),
    enabled: canFetchPreview && Boolean(activeDocument),
    retry: false,
  });

  const preview = previewQuery.data ?? null;
  const title = preview?.name || source?.documentTitle || 'Source';
  const openUrl = preview?.open_url ? apiUrl(preview.open_url) : source?.fileUrl ? apiUrl(source.fileUrl) : null;
  const downloadUrl = preview?.download_url ? apiUrl(preview.download_url) : null;
  const pageNumber = activePage ?? preview?.page ?? source?.pageNumber ?? 1;
  const effectivePageCount = preview?.page_count ?? preview?.slides?.length ?? pageCount ?? source?.pageCount ?? null;
  const showUnavailablePreview = Boolean(source) && !canFetchPreview;
  const searchEnabled = Boolean(
    preview
    && !['docx', 'markdown', 'html', 'image'].includes(preview.render_kind || '')
    && preview.render_kind !== 'image'
    && (preview.preview_text || preview.table_rows?.length || preview.slides?.length || preview.rendered_html),
  );
  const pageLabel = preview?.render_kind === 'slides' ? 'Slide' : 'Page';

  useEffect(() => {
    if (preview?.page_count) setPageCount(preview.page_count);
    else if (preview?.slides?.length) setPageCount(preview.slides.length);
  }, [preview?.page_count, preview?.slides?.length]);

  if (!source) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">Source Viewer</h2>
          <button type="button" onClick={onClose} className="ce-icon-button" aria-label="Close source viewer">Close</button>
        </div>
        <div className="flex flex-1 items-center justify-center p-6">
          <div className="rounded-2xl border border-dashed border-border bg-muted p-5 text-center">
            <FileSearch className="mx-auto mb-2 text-muted-foreground" size={28} />
            <p className="text-sm font-semibold text-foreground">No source selected</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-white" data-testid="document-viewer-panel">
      <DocumentToolbar
        title={title}
        documentId={activeDocument}
        citationIndex={source.citationIndex}
        pageNumber={pageNumber}
        pageCount={effectivePageCount}
        pageLabel={pageLabel}
        fileType={preview?.file_type || source.fileType}
        currentIndex={Math.max(0, currentIndex)}
        total={sources.length}
        previousSource={previousSource}
        nextSource={nextSource}
        searchValue={searchQuery}
        searchEnabled={searchEnabled}
        zoomLevel={zoomLevel}
        onPrevious={() => previousSource && onSelectSource(previousSource)}
        onNext={() => nextSource && onSelectSource(nextSource)}
        onClose={onClose}
        onSearchChange={setSearchQuery}
        onZoomIn={() => setZoomLevel((current) => Math.min(current + 0.1, 2))}
        onZoomOut={() => setZoomLevel((current) => Math.max(current - 0.1, 0.7))}
        onZoomReset={() => setZoomLevel(1)}
        onPageChange={(value) => {
          const nextValue = effectivePageCount ? Math.min(Math.max(value, 1), effectivePageCount) : Math.max(value, 1);
          setActivePage(nextValue);
          setPreviewPage(nextValue);
          setActiveChunk(null);
        }}
        openUrl={openUrl}
        downloadUrl={downloadUrl}
      />

      <div className="scrollbar-soft min-h-0 flex-1 overflow-y-auto p-5">
        {previewQuery.isLoading ? (
          <div className="rounded-2xl border border-border bg-[hsl(210_20%_98%)] p-4 text-sm text-muted-foreground">
            Loading preview and source metadata...
          </div>
        ) : null}

        {previewQuery.isError ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-700">
            The document preview could not be loaded. The cited excerpt is still available below.
          </div>
        ) : null}

        {showUnavailablePreview ? (
          <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
            <div className="flex items-start gap-2">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>This citation could not be matched to a previewable document record. The viewer is showing the cited excerpt and source metadata only.</span>
            </div>
          </div>
        ) : null}

        {preview?.preview_notice ? (
          <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">
            {preview.preview_notice}
          </div>
        ) : null}

        <div className="flex flex-col gap-4">
          {/* CTA card to open full workspace */}
          <div className="rounded-2xl border border-[#e3e9e1] bg-[#edf6e9]/40 p-4 text-center">
            <Sparkles className="mx-auto mb-2 text-[#2f6d25]" size={20} />
            <h3 className="text-sm font-semibold text-slate-900">Inspect Full Document Workspace</h3>
            <p className="mt-1 text-xs text-slate-600 mb-3">
              View this document in high fidelity, search text, and run deep AI queries in the full workspace.
            </p>
            <Link
              href={`/knowledge/document/${activeDocument}?page=${pageNumber ?? 1}`}
              className="ce-action ce-action-primary h-9 px-4 inline-flex items-center justify-center rounded-xl text-xs font-semibold"
            >
              Open Full Workspace
            </Link>
          </div>

          <div className="space-y-4">
            <HighlightExcerpt
              text={source.previewText || source.excerpt}
              highlight={preview?.highlight_text || source.highlightText || source.excerpt}
            />
            <div className="rounded-2xl border border-border bg-white p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Document excerpt</p>
              <p className="safe-text whitespace-pre-wrap text-sm leading-6 text-foreground font-sans">
                {preview?.preview_text || source.previewText || source.excerpt || 'No preview text is available for this document.'}
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-[hsl(210_20%_98%)] p-4 text-xs">
            <h3 className="text-sm font-semibold text-foreground mb-4">Document details</h3>
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <dt className="font-semibold text-muted-foreground">Relative path</dt>
                <dd className="safe-text mt-1 text-foreground">{preview?.relative_path || source.relativePath || source.documentId}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Type</dt>
                <dd className="mt-1 text-foreground">{preview?.file_type || source.fileType || 'Unknown'}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Size</dt>
                <dd className="mt-1 text-foreground">{formatBytes(preview?.size_bytes)}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Index status</dt>
                <dd className="mt-1 text-foreground">{preview?.indexing_status || 'Unknown'}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Modified</dt>
                <dd className="mt-1 text-foreground">{preview?.modified_at ? new Date(preview.modified_at).toLocaleString() : 'Unknown'}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Pages / sheets</dt>
                <dd className="mt-1 text-foreground">{effectivePageCount ?? preview?.sheet_count ?? 'n/a'}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Extraction</dt>
                <dd className="mt-1 text-foreground">{preview?.extraction_method || 'metadata'}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">{pageLabel}</dt>
                <dd className="mt-1 text-foreground">{pageNumber || 'n/a'}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="font-semibold text-muted-foreground">Chunk</dt>
                <dd className="safe-text mt-1 text-foreground break-all">{activeChunk || preview?.chunk_id || source.chunkId || 'n/a'}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}
