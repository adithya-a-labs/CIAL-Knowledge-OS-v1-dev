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
  const currentIndex = source ? sources.findIndex((candidate) => candidate.id === source.id) : -1;
  const previousSource = currentIndex > 0 ? sources[currentIndex - 1] : null;
  const nextSource = currentIndex >= 0 && currentIndex < sources.length - 1 ? sources[currentIndex + 1] : null;
  const canFetchPreview = looksLikeUuid(source?.documentId);
  const previewQuery = useQuery({
    queryKey: ['document-preview', source?.documentId, source?.chunkId, source?.pageNumber],
    queryFn: () => getDocumentPreview(source!.documentId, source?.chunkId, source?.pageNumber),
    enabled: Boolean(source && canFetchPreview),
    retry: false,
  });
  const preview = previewQuery.data ?? null;
  const title = preview?.name || source?.documentTitle || 'Source';
  const openUrl = preview?.open_url ? apiUrl(preview.open_url) : null;
  const downloadUrl = preview?.download_url ? apiUrl(preview.download_url) : null;

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

  const showUnavailablePreview = !canFetchPreview;

  return (
    <div className="flex h-full flex-col" data-testid="document-viewer-panel">
      <DocumentToolbar
        title={title}
        citationIndex={source.citationIndex}
        pageNumber={source.pageNumber}
        currentIndex={Math.max(0, currentIndex)}
        total={sources.length}
        previousSource={previousSource}
        nextSource={nextSource}
        onPrevious={() => previousSource && onSelectSource(previousSource)}
        onNext={() => nextSource && onSelectSource(nextSource)}
        onClose={onClose}
        openUrl={openUrl}
        downloadUrl={downloadUrl}
      />

      <div className="scrollbar-soft flex-1 space-y-3 overflow-y-auto p-4">
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
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
            <div className="flex items-start gap-2">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>This citation could not be matched to a previewable document record. The viewer is showing the cited excerpt and source metadata only.</span>
            </div>
          </div>
        ) : null}

        <DocumentPreviewRenderer preview={preview} title={title} />
        <HighlightExcerpt text={source.excerpt} highlight={preview?.highlight_text || source.excerpt} />

        <dl className="grid grid-cols-1 gap-2 rounded-2xl border border-border bg-white p-3 text-xs sm:grid-cols-2">
          <div>
            <dt className="font-semibold text-muted-foreground">Relative path</dt>
            <dd className="safe-text mt-1 text-foreground">{preview?.relative_path || source.relativePath || source.documentId}</dd>
          </div>
          <div>
            <dt className="font-semibold text-muted-foreground">Type</dt>
            <dd className="mt-1 text-foreground">{preview?.file_type || 'Unknown'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-muted-foreground">Size</dt>
            <dd className="mt-1 text-foreground">{formatBytes(preview?.size_bytes)}</dd>
          </div>
          <div>
            <dt className="font-semibold text-muted-foreground">Index status</dt>
            <dd className="mt-1 text-foreground" title="pending means metadata synced but not vector indexed; indexing is in progress; indexed is searchable; failed needs attention; deleted was removed from the corpus source.">{preview?.indexing_status || 'Unknown'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-muted-foreground">Modified</dt>
            <dd className="mt-1 text-foreground">{preview?.modified_at ? new Date(preview.modified_at).toLocaleString() : 'Unknown'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-muted-foreground">Pages / sheets</dt>
            <dd className="mt-1 text-foreground">{preview?.page_count ?? preview?.sheet_count ?? 'n/a'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-muted-foreground">Extraction</dt>
            <dd className="mt-1 text-foreground">{preview?.extraction_method || 'metadata'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-muted-foreground">Page</dt>
            <dd className="mt-1 text-foreground">{source.pageNumber ?? preview?.page ?? 'n/a'}</dd>
          </div>
          <div>
            <dt className="font-semibold text-muted-foreground">Chunk</dt>
            <dd className="safe-text mt-1 text-foreground">{source.chunkId ?? preview?.chunk_id ?? 'n/a'}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
