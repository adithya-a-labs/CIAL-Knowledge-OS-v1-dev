import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileSearch } from 'lucide-react';
import { Link } from 'wouter';
import { apiUrl, getDocumentPreview } from '@/api/client';
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

function PdfFallback({
  documentId,
  excerpt,
  pageNumber,
}: {
  documentId?: string | null;
  excerpt: string;
  pageNumber?: number | null;
}) {
  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-[#f7f9f6] px-6 py-8">
      <div className="w-full max-w-xl rounded-xl border border-[#dce4d8] bg-white p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[#eef5e8] text-primary">
            <FileSearch size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-slate-950">Inline PDF preview unavailable</h3>
            <p className="mt-1 text-xs leading-5 text-slate-600">
              The cited content is still available below, and the full document workspace opens at the cited page.
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Cited excerpt</p>
          <p className="safe-text mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{excerpt}</p>
        </div>

        {documentId ? (
          <Link
            href={`/knowledge/document/${documentId}?page=${pageNumber ?? 1}`}
            className="mt-4 inline-flex h-9 items-center justify-center rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground transition hover:opacity-95"
          >
            Open Full Workspace
          </Link>
        ) : null}
      </div>
    </div>
  );
}

function NativePdfFrame({ src, title }: { src: string; title: string }) {
  return (
    <iframe
      src={src}
      title={title}
      className="h-full w-full border-0 bg-white"
      referrerPolicy="no-referrer"
    />
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

  const previewQuery = useQuery({
    queryKey: ['assistant-source-preview', source?.documentId, source?.chunkId, source?.pageNumber],
    queryFn: () => getDocumentPreview(source!.documentId, source?.chunkId, source?.pageNumber),
    enabled: Boolean(source?.documentId),
    retry: false,
  });

  const preview = previewQuery.data ?? null;
  const title = preview?.name || source?.documentTitle || 'Source';
  const pageNumber = source?.pageNumber ?? preview?.page ?? 1;
  const pdfViewerUrl = useMemo(() => {
    if (source?.fileUrl && source.fileType?.toLowerCase() === 'pdf') {
      return `${apiUrl(source.fileUrl)}#page=${pageNumber}`;
    }

    if (!preview) return null;

    if (preview.viewer_ready && preview.viewer_format === 'pdf' && preview.viewer_url) {
      return `${apiUrl(preview.viewer_url)}#page=${pageNumber}`;
    }

    if (preview.render_kind === 'pdf') {
      const directUrl = preview.file_url || preview.open_url;
      return directUrl ? `${apiUrl(directUrl)}#page=${pageNumber}` : null;
    }

    return null;
  }, [pageNumber, preview, source?.fileType, source?.fileUrl]);
  const fallbackExcerpt = excerptFor(source, preview?.preview_text);

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

  const fallback = (
    <PdfFallback
      documentId={source.documentId}
      excerpt={fallbackExcerpt}
      pageNumber={pageNumber}
    />
  );

  return (
    <div className="flex h-full min-h-0 flex-col bg-white" data-testid="document-viewer-panel">
      <DocumentToolbar
        title={title}
        documentId={source.documentId}
        citationIndex={source.citationIndex}
        pageNumber={pageNumber}
        currentIndex={Math.max(0, currentIndex)}
        total={sources.length}
        previousSource={previousSource}
        nextSource={nextSource}
        onPrevious={() => previousSource && onSelectSource(previousSource)}
        onNext={() => nextSource && onSelectSource(nextSource)}
        onClose={onClose}
      />

      <div className="min-h-0 flex-1 overflow-hidden bg-[#f7f9f6]">
        {pdfViewerUrl ? (
          <NativePdfFrame src={pdfViewerUrl} title={title} />
        ) : previewQuery.isLoading ? (
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-500">
            Loading PDF...
          </div>
        ) : (
          fallback
        )}
      </div>
    </div>
  );
}
