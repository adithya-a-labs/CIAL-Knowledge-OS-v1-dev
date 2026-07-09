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
  FileText,
  Info,
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

function detailRows(document: CorpusDocument | null, pageCount: number | null, extraction?: string) {
  return [
    ['Relative path', document?.relative_path || 'Unknown'],
    ['Type', document?.file_type || document?.extension || 'Unknown'],
    ['MIME type', document?.mime_type || 'Unknown'],
    ['Size', formatBytes(document?.size_bytes)],
    ['Index status', document?.indexing_status || 'Unknown'],
    ['Indexed', document?.indexed ? 'Yes' : 'No'],
    ['Pages / sheets', pageCount ? String(pageCount) : 'n/a'],
    ['Modified', formatDate(document?.modified_at)],
    ['Created', formatDate(document?.created_at)],
    ['Updated', formatDate(document?.updated_at)],
    ['Extraction', extraction || 'metadata'],
    ['Content hash', document?.content_hash || 'n/a'],
  ];
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
  const rows = useMemo(
    () => detailRows(document, effectivePageCount, preview?.extraction_method),
    [document, effectivePageCount, preview?.extraction_method],
  );

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
      <div className="mb-3 flex shrink-0 flex-col gap-3 rounded-xl border border-slate-200 bg-white px-3 py-3 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <button type="button" onClick={goBack} className="ce-icon-button h-10 w-10 shrink-0" aria-label="Back to Knowledge Center">
            <ArrowLeft size={18} />
          </button>
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h1 className="safe-text min-w-0 text-base font-semibold text-slate-950 sm:text-lg">{title}</h1>
              <span className="ce-badge px-2 py-1 text-xs">{(document?.extension || document?.file_type || 'file').replace('.', '').toUpperCase()}</span>
              <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${statusTone(document?.indexing_status)}`}>
                {document?.indexing_status || 'unknown'}
              </span>
            </div>
            <p className="safe-text mt-1 text-xs text-slate-500">{document?.relative_path || documentId}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="hidden h-10 min-w-0 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-500 md:flex">
            <Search size={15} />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search preview"
              className="w-36 bg-transparent text-slate-800 placeholder:text-slate-400"
              type="search"
            />
          </label>
          <button type="button" onClick={() => setZoomLevel((current) => Math.max(current - 0.1, 0.7))} className="ce-icon-button h-10 w-10" aria-label="Zoom out"><Minus size={16} /></button>
          <button type="button" onClick={() => setZoomLevel(1)} className="ce-icon-button h-10 w-10" aria-label="Reset zoom"><RotateCcw size={16} /></button>
          <button type="button" onClick={() => setZoomLevel((current) => Math.min(current + 0.1, 2))} className="ce-icon-button h-10 w-10" aria-label="Zoom in"><Plus size={16} /></button>
          <a href={viewUrl} target="_blank" rel="noreferrer" className="ce-action h-10 px-3">
            <ExternalLink size={15} />Open
          </a>
          <a href={downloadUrl} className="ce-action h-10 px-3">
            <Download size={15} />Download
          </a>
          <button type="button" onClick={useInAssistant} disabled={!document || unavailable} className="ce-action ce-action-primary h-10 px-3 disabled:opacity-50">
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
        <div className="grid min-h-0 flex-1 gap-3 overflow-hidden xl:grid-cols-[minmax(0,1fr)_22rem]">
          <main className="min-h-0 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            {previewQuery.isLoading ? (
              <div className="flex h-full min-h-[28rem] items-center justify-center text-sm text-slate-500">Loading preview...</div>
            ) : previewQuery.isError ? (
              <div className="flex h-full min-h-[28rem] items-center justify-center p-6">
                <div className="max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-5 text-center text-sm text-amber-900">
                  <AlertTriangle className="mx-auto mb-3" size={28} />
                  <p className="font-semibold">Preview unavailable</p>
                  <p className="mt-2 leading-6">The file metadata loaded, but the preview endpoint did not. Use Open or Download, or inspect the metadata panel.</p>
                </div>
              </div>
            ) : (
              <div className="h-full min-h-[28rem] p-3">
                {preview?.preview_notice ? (
                  <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                    {preview.preview_notice}
                  </div>
                ) : null}
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
            )}
          </main>

          <aside className="scrollbar-soft min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                <Info size={16} className="text-primary" />
                Document details
              </div>
            </div>
            <div className="space-y-5 p-4">
              <section>
                <h2 className="text-xs font-semibold uppercase text-slate-500">Metadata</h2>
                <dl className="mt-3 space-y-3 text-xs">
                  {rows.map(([label, value]) => (
                    <div key={label} className="grid gap-1">
                      <dt className="font-semibold text-slate-500">{label}</dt>
                      <dd className="safe-text text-slate-900">{value}</dd>
                    </div>
                  ))}
                </dl>
              </section>

              <section>
                <h2 className="text-xs font-semibold uppercase text-slate-500">Extracted text</h2>
                <div className="mt-3 max-h-80 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p className="safe-text whitespace-pre-wrap text-xs leading-5 text-slate-700">
                    {preview?.preview_text || 'No extracted text is available for this file. Open or download the source document to inspect it.'}
                  </p>
                </div>
              </section>

              <section>
                <h2 className="text-xs font-semibold uppercase text-slate-500">Related context</h2>
                <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600">
                  <div className="flex items-start gap-2">
                    <FileText size={14} className="mt-0.5 shrink-0 text-primary" />
                    <span>Use this document in AI Assistant to scope answers to the selected source.</span>
                  </div>
                </div>
              </section>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
