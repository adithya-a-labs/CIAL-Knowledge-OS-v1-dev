import { useEffect, useMemo, useState } from 'react';
import type React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useParams } from 'wouter';
import {
  AlertTriangle,
  ArrowLeft,
  Download,
  ExternalLink,
  FileSearch,
  Minus,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
} from 'lucide-react';
import {
  apiUrl,
  getCorpusDocument,
  getDocumentDownloadUrl,
  getDocumentPreview,
  getDocumentViewUrl,
} from '@/api/client';
import { corpusDocumentToContext } from '@/api/adapters';
import type { CorpusDocument } from '@/api/types';
import DocumentPreviewRenderer from '@/components/assistant/DocumentPreviewRenderer';

const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_CONTEXT_INTENT_STORAGE_KEY = 'cial-assistant-context-intent';

function formatBytes(value?: number | null) {
  if (!value) return 'Unknown size';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value?: string | null) {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function statusTone(status?: string | null) {
  if (status === 'indexed') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'failed' || status === 'deleted') return 'border-red-200 bg-red-50 text-red-700';
  if (status === 'indexing' || status === 'pending') return 'border-amber-200 bg-amber-50 text-amber-800';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function UnavailableState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[28rem] items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center">
      <div className="max-w-md">
        <FileSearch className="mx-auto text-slate-400" size={34} />
        <h1 className="mt-4 text-lg font-semibold text-slate-950">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">{message}</p>
        {action ? <div className="mt-5">{action}</div> : null}
      </div>
    </div>
  );
}

export default function DocumentWorkspacePage() {
  const params = useParams<{ documentId: string }>();
  const [, navigate] = useLocation();
  const documentId = params.documentId;

  const queryParams = new URLSearchParams(window.location.search);
  const pageParam = queryParams.get('page');
  const initialPage = pageParam ? parseInt(pageParam, 10) || 1 : 1;

  const [zoomLevel, setZoomLevel] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState(initialPage);
  const [requestedPage, setRequestedPage] = useState(initialPage);
  const [pageCount, setPageCount] = useState<number | null>(null);

  const documentQuery = useQuery({
    queryKey: ['corpus-document', documentId],
    queryFn: () => getCorpusDocument(documentId),
    enabled: Boolean(documentId),
    retry: false,
  });

  const previewQuery = useQuery({
    queryKey: ['document-workspace-preview', documentId, requestedPage],
    queryFn: () => getDocumentPreview(documentId, undefined, requestedPage),
    enabled: Boolean(documentId) && !documentQuery.isError,
    retry: false,
  });

  const document = documentQuery.data ?? null;
  const preview = previewQuery.data ?? null;
  const title = preview?.name || document?.name || 'Document';
  const viewUrl = preview?.open_url ? apiUrl(preview.open_url) : getDocumentViewUrl(documentId);
  const downloadUrl = preview?.download_url ? apiUrl(preview.download_url) : getDocumentDownloadUrl(documentId);
  const effectivePageCount = preview?.page_count ?? preview?.slides?.length ?? pageCount ?? null;
  const typeLabel = useMemo(
    () => (document?.extension || document?.file_type || 'file').replace('.', '').toUpperCase(),
    [document?.extension, document?.file_type],
  );
  const canOpenInline = preview ? preview.viewer_ready !== false : true;
  const viewerMode = preview?.viewer_format?.replace(/^\./, '').toLowerCase() || '';
  const showExtractedTextFallback = useMemo(() => {
    if (!preview?.preview_text) return false;
    if (preview.render_kind === 'card') return true;
    if (preview.render_kind === 'pdf' || preview.render_kind === 'image') return true;
    if (preview.viewer_ready && ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'bmp'].includes(viewerMode)) return true;
    return false;
  }, [preview?.preview_text, preview?.render_kind, preview?.viewer_ready, viewerMode]);

  useEffect(() => {
    if (preview?.page_count) setPageCount(preview.page_count);
    else if (preview?.slides?.length) setPageCount(preview.slides.length);
  }, [preview?.page_count, preview?.slides?.length]);

  useEffect(() => {
    const qParams = new URLSearchParams(window.location.search);
    const pVal = qParams.get('page');
    if (pVal) {
      const page = parseInt(pVal, 10);
      if (page && page !== requestedPage) {
        setActivePage(page);
        setRequestedPage(page);
      }
    }
  }, [window.location.search]);

  const useInAssistant = () => {
    if (!document) return;
    window.localStorage.setItem(ASSISTANT_CONTEXT_STORAGE_KEY, JSON.stringify([corpusDocumentToContext(document)]));
    window.localStorage.setItem(ASSISTANT_CONTEXT_INTENT_STORAGE_KEY, String(Date.now()));
    navigate('/assistant');
  };

  const goBack = () => {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    navigate('/knowledge-center');
  };

  if (documentQuery.isLoading) {
    return (
      <div className="flex h-full min-h-[32rem] items-center justify-center" data-testid="document-workspace-loading">
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600 shadow-sm">
          Loading document workspace...
        </div>
      </div>
    );
  }

  if (documentQuery.isError) {
    return (
      <UnavailableState
        title="Document not found"
        message="The document may have been removed, is unavailable, or the backend could not resolve its metadata."
        action={<Link href="/knowledge-center" className="ce-action ce-action-primary min-h-10 px-4">Back to Knowledge Center</Link>}
      />
    );
  }

  const unavailable = document?.indexing_status === 'deleted';

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden" data-testid="document-workspace-page">
      <div className="mb-2 flex shrink-0 flex-col gap-2 border-b border-slate-200 bg-white px-3 py-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <button type="button" onClick={goBack} className="ce-icon-button h-9 w-9 shrink-0" aria-label="Back to Knowledge Center">
            <ArrowLeft size={18} />
          </button>
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h1 className="safe-text min-w-0 text-base font-semibold text-slate-950 sm:text-lg">{title}</h1>
              <span className="ce-badge px-2 py-1 text-[11px]">{typeLabel}</span>
              <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${statusTone(document?.indexing_status)}`}>
                {document?.indexing_status || 'unknown'}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
              <span>{formatBytes(document?.size_bytes)}</span>
              <span>{effectivePageCount ? `${effectivePageCount} ${preview?.slides?.length ? 'slides' : 'pages'}` : 'Preview workspace'}</span>
              <span>Updated {formatDate(document?.updated_at || document?.modified_at)}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="hidden h-9 min-w-0 items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-500 md:flex">
            <Search size={15} />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search preview"
              className="w-36 bg-transparent text-slate-800 placeholder:text-slate-400"
              type="search"
            />
          </label>
          <button type="button" onClick={() => setZoomLevel((current) => Math.max(current - 0.1, 0.7))} className="ce-icon-button h-9 w-9" aria-label="Zoom out"><Minus size={16} /></button>
          <button type="button" onClick={() => setZoomLevel(1)} className="ce-icon-button h-9 w-9" aria-label="Reset zoom"><RotateCcw size={16} /></button>
          <button type="button" onClick={() => setZoomLevel((current) => Math.min(current + 0.1, 2))} className="ce-icon-button h-9 w-9" aria-label="Zoom in"><Plus size={16} /></button>
          {canOpenInline ? (
            <a href={viewUrl} target="_blank" rel="noreferrer" className="ce-action h-9 px-3">
              <ExternalLink size={15} />Open
            </a>
          ) : (
            <span
              className="ce-action h-9 cursor-not-allowed px-3 opacity-60"
              aria-disabled="true"
              title="Inline open is unavailable for this file type. Use the workspace preview or Download."
            >
              <ExternalLink size={15} />Open
            </span>
          )}
          <a href={downloadUrl} className="ce-action h-9 px-3">
            <Download size={15} />Download
          </a>
          <button type="button" onClick={useInAssistant} disabled={!document || unavailable} className="ce-action ce-action-primary h-9 px-3 disabled:opacity-50">
            <Sparkles size={15} />Ask AI
          </button>
        </div>
      </div>

      {unavailable ? (
        <UnavailableState
          title="Document unavailable"
          message="This document record exists, but the source file is marked deleted or unavailable. Metadata remains visible for audit and recovery."
        />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <main className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
            {previewQuery.isLoading ? (
              <div className="flex h-full min-h-[28rem] items-center justify-center text-sm text-slate-500">Loading preview...</div>
            ) : previewQuery.isError ? (
              <div className="flex h-full min-h-[28rem] items-center justify-center p-6">
                <div className="max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-5 text-center text-sm text-amber-900">
                  <AlertTriangle className="mx-auto mb-3" size={28} />
                  <p className="font-semibold">Preview unavailable</p>
                  <p className="mt-2 leading-6">The metadata loaded, but the preview endpoint did not return a usable inline preview. Use Open or Download to inspect the source document.</p>
                </div>
              </div>
            ) : (
              <div className="flex min-h-0 flex-1 flex-col">
                {preview?.preview_notice ? (
                  <div className="border-b border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                    {preview.preview_notice}
                  </div>
                ) : null}
                <div className="min-h-0 flex-1 p-3">
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
                </div>
                {showExtractedTextFallback ? (
                  <section className="border-t border-slate-200 bg-slate-50/70 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Extracted text fallback</p>
                    <div className="scrollbar-soft mt-2 max-h-40 overflow-auto rounded-lg border border-slate-200 bg-white p-3">
                      <p className="safe-text whitespace-pre-wrap text-xs leading-5 text-slate-700">
                        {preview?.preview_text || 'Extracted text is unavailable for this document.'}
                      </p>
                    </div>
                  </section>
                ) : null}
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
}
