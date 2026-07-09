import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, FileSearch } from 'lucide-react';
import { apiUrl, getDocumentPreview } from '@/api/client';
import DocumentPreviewRenderer from './DocumentPreviewRenderer';
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
  const [activeChunk, setActiveChunk] = useState<string | null>(source?.chunkId ?? null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    setActiveDocument(source?.documentId ?? null);
    setActivePage(source?.pageNumber ?? null);
    setActiveChunk(source?.chunkId ?? null);
    setZoomLevel(1);
    setSearchQuery('');
  }, [source?.documentId, source?.pageNumber, source?.chunkId, source?.id]);

  const currentIndex = source ? sources.findIndex((candidate) => candidate.id === source.id) : -1;
  const previousSource = currentIndex > 0 ? sources[currentIndex - 1] : null;
  const nextSource = currentIndex >= 0 && currentIndex < sources.length - 1 ? sources[currentIndex + 1] : null;
  const canFetchPreview = looksLikeUuid(activeDocument ?? undefined);

  const previewQuery = useQuery({
    queryKey: ['document-preview', activeDocument, activeChunk, activePage],
    queryFn: () => getDocumentPreview(activeDocument!, activeChunk ?? undefined, activePage ?? undefined),
    enabled: canFetchPreview && Boolean(activeDocument),
    retry: false,
  });

  const preview = previewQuery.data ?? null;
  const title = preview?.name || source?.documentTitle || 'Source';
  const openUrl = preview?.open_url ? apiUrl(preview.open_url) : source?.fileUrl ? apiUrl(source.fileUrl) : null;
  const downloadUrl = preview?.download_url ? apiUrl(preview.download_url) : null;
  const pageNumber = activePage ?? preview?.page ?? source?.pageNumber ?? 1;
  const pageCount = preview?.page_count ?? preview?.slides?.length ?? source?.pageCount ?? null;
  const showUnavailablePreview = Boolean(source) && !canFetchPreview;
  const searchEnabled = Boolean(
    preview
    && preview.render_kind !== 'pdf'
    && preview.render_kind !== 'image'
    && (preview.preview_text || preview.table_rows?.length || preview.slides?.length || preview.rendered_html),
  );

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
        citationIndex={source.citationIndex}
        pageNumber={pageNumber}
        pageCount={pageCount}
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
        onPageChange={(value) => {
          setActivePage(pageCount ? Math.min(Math.max(value, 1), pageCount) : Math.max(value, 1));
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

        <div className="grid gap-4 xl:grid-rows-[minmax(28rem,3fr)_auto]">
          <div className="min-h-[28rem]">
            <DocumentPreviewRenderer preview={preview} title={title} searchQuery={searchQuery} zoomLevel={zoomLevel} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
            <div className="space-y-4">
              <HighlightExcerpt
                text={source.previewText || source.excerpt}
                highlight={preview?.highlight_text || source.highlightText || source.excerpt}
              />
              <div className="rounded-2xl border border-border bg-white p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Document excerpt</p>
                <p className="safe-text whitespace-pre-wrap text-sm leading-6 text-foreground">
                  {preview?.preview_text || source.previewText || source.excerpt || 'No preview text is available for this document.'}
                </p>
              </div>
            </div>

            <dl className="grid grid-cols-1 gap-3 rounded-2xl border border-border bg-[hsl(210_20%_98%)] p-4 text-xs sm:grid-cols-2 xl:grid-cols-1">
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
                <dd className="mt-1 text-foreground">{pageCount ?? preview?.sheet_count ?? 'n/a'}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Extraction</dt>
                <dd className="mt-1 text-foreground">{preview?.extraction_method || 'metadata'}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Page</dt>
                <dd className="mt-1 text-foreground">{pageNumber || 'n/a'}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted-foreground">Chunk</dt>
                <dd className="safe-text mt-1 text-foreground">{activeChunk || preview?.chunk_id || source.chunkId || 'n/a'}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}
