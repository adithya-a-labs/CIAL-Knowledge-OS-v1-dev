import { useEffect, useMemo, useRef, useState } from 'react';
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
  PanelLeftClose,
  PanelRightClose,
  RefreshCw,
  Upload,
} from 'lucide-react';
import {
  apiUrl,
  getCorpusDocument,
  getDocumentDownloadUrl,
  getDocumentPreview,
  getDocumentViewUrl,
  getCorpusTree,
} from '@/api/client';
import { corpusDocumentToContext } from '@/api/adapters';
import type { CorpusDocument } from '@/api/types';
import DocumentPreviewRenderer from '@/components/assistant/DocumentPreviewRenderer';
import FileIndexingStatus from '@/components/documents/FileIndexingStatus';
import CorpusTreePanel from '@/components/knowledge-center/CorpusTreePanel';
import DocumentAssistantPanel from '@/components/knowledge-center/DocumentAssistantPanel';
import { useCommandPalette } from '@/components/common/CommandPalette';
import { createConversationHandoff } from '@/lib/conversationHandoff';
import { cn } from '@/lib/utils';

const CORPUS_TREE_PERSISTENT_QUERY = '(min-width: 1280px)';
const DOCUMENT_ASSISTANT_PERSISTENT_QUERY = '(min-width: 1024px)';

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

function readPanelWidth(key: string, fallback: number) {
  const value = Number(window.localStorage.getItem(key));
  return Number.isFinite(value) && value >= 220 && value <= 520 ? value : fallback;
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
    <div className="flex min-h-[28rem] items-center justify-center rounded-xl border border-dashed border-border bg-card p-6 text-center">
      <div className="max-w-md">
        <FileSearch className="mx-auto text-muted-foreground" size={34} />
        <h1 className="mt-4 text-lg font-semibold text-foreground">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{message}</p>
        {action ? <div className="mt-5">{action}</div> : null}
      </div>
    </div>
  );
}

export default function DocumentWorkspacePage() {
  const params = useParams<{ documentId: string }>();
  const [, navigate] = useLocation();
  const documentId = params.documentId;
  const {setOpen:setSearchOpen}=useCommandPalette();
  const[leftOpen,setLeftOpen]=useState(
    ()=>window.matchMedia(CORPUS_TREE_PERSISTENT_QUERY).matches
      && localStorage.getItem('cial-kc-left-open')!=='false',
  );
  const[rightOpen,setRightOpen]=useState(
    ()=>window.matchMedia(DOCUMENT_ASSISTANT_PERSISTENT_QUERY).matches
      && localStorage.getItem('cial-kc-right-open')!=='false',
  );
  const[corpusTreePersistent,setCorpusTreePersistent]=useState(
    ()=>window.matchMedia(CORPUS_TREE_PERSISTENT_QUERY).matches,
  );
  const[documentAssistantPersistent,setDocumentAssistantPersistent]=useState(
    ()=>window.matchMedia(DOCUMENT_ASSISTANT_PERSISTENT_QUERY).matches,
  );
  const leftPanelRef=useRef<HTMLElement>(null);
  const rightPanelRef=useRef<HTMLElement>(null);
  const [leftWidth,setLeftWidth]=useState(()=>readPanelWidth('cial-kc-left-width',280));
  const [rightWidth,setRightWidth]=useState(()=>readPanelWidth('cial-kc-right-width',384));

  const queryParams = new URLSearchParams(window.location.search);
  const pageParam = queryParams.get('page');
  const slideParam = queryParams.get('slide');
  const sheetParam = queryParams.get('sheet');
  const sheetIndexParam = queryParams.get('sheetIndex');
  const chunkParam = queryParams.get('chunk');
  const initialSlideNumber = slideParam ? parseInt(slideParam, 10) || 1 : null;
  const initialPage = pageParam ? parseInt(pageParam, 10) || 1 : 1;

  const [zoomLevel, setZoomLevel] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState(initialPage);
  const [requestedPage, setRequestedPage] = useState(initialPage);
  const [requestedSlideNumber, setRequestedSlideNumber] = useState<number | null>(initialSlideNumber);
  const [requestedSheetName, setRequestedSheetName] = useState<string | null>(sheetParam);
  const [requestedSheetIndex, setRequestedSheetIndex] = useState<number | null>(
    sheetIndexParam ? parseInt(sheetIndexParam, 10) || 1 : null,
  );
  const [requestedChunkId, setRequestedChunkId] = useState<string | null>(chunkParam);
  const [pageCount, setPageCount] = useState<number | null>(null);

  const documentQuery = useQuery({
    queryKey: ['corpus-document', documentId],
    queryFn: () => getCorpusDocument(documentId),
    enabled: Boolean(documentId),
    retry: false,
    refetchInterval: (query) => ['pending', 'indexing'].includes(query.state.data?.indexing_status || '') ? 1500 : false,
  });

  const previewQuery = useQuery({
    queryKey: ['document-workspace-preview', documentId, requestedPage, requestedSlideNumber, requestedSheetName, requestedSheetIndex, requestedChunkId],
    queryFn: () => getDocumentPreview(documentId, {
      chunkId: requestedChunkId ?? undefined,
      page: requestedPage,
      sheetName: requestedSheetName ?? undefined,
      sheetIndex: requestedSheetIndex ?? undefined,
      slideNumber: requestedSlideNumber ?? undefined,
    }),
    enabled: Boolean(documentId) && !documentQuery.isError,
    retry: false,
  });
  const treeQuery=useQuery({queryKey:['corpus-tree'],queryFn:getCorpusTree,retry:false,staleTime:60_000});

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

  useEffect(() => {
    if (preview?.page_count) setPageCount(preview.page_count);
    else if (preview?.slides?.length) setPageCount(preview.slides.length);
  }, [preview?.page_count, preview?.slides?.length]);

  useEffect(() => {
    const qParams = new URLSearchParams(window.location.search);
    const pVal = qParams.get('page');
    const slideVal = qParams.get('slide');
    const sheetVal = qParams.get('sheet');
    const sheetIndexVal = qParams.get('sheetIndex');
    const chunkVal = qParams.get('chunk');
    if (pVal) {
      const page = parseInt(pVal, 10);
      if (page && page !== requestedPage) {
        setActivePage(page);
        setRequestedPage(page);
      }
    }
    const nextSlide = slideVal ? parseInt(slideVal, 10) || 1 : null;
    if (nextSlide !== requestedSlideNumber) {
      setRequestedSlideNumber(nextSlide);
      if (nextSlide) {
        setActivePage(nextSlide);
        setRequestedPage(nextSlide);
      }
    }
    if ((sheetVal || null) !== requestedSheetName) {
      setRequestedSheetName(sheetVal || null);
    }
    const nextSheetIndex = sheetIndexVal ? parseInt(sheetIndexVal, 10) || 1 : null;
    if (nextSheetIndex !== requestedSheetIndex) {
      setRequestedSheetIndex(nextSheetIndex);
    }
    if ((chunkVal || null) !== requestedChunkId) {
      setRequestedChunkId(chunkVal || null);
    }
  }, [window.location.search]);

  const useInAssistant = async (question?:string) => {
    if (!document) return;
    createConversationHandoff(navigate,{title:`${document.name} · document chat`,origin:'knowledge_center',created_from_document:document.id,context_scope:'selected_documents',selected_document_ids:[document.id],question,autoSubmit:Boolean(question?.trim()),contextItems:[{...corpusDocumentToContext(document),page_number:activePage,chunk_id:requestedChunkId??undefined}]});
  };

  useEffect(()=>{
    const corpusTreeMedia=window.matchMedia(CORPUS_TREE_PERSISTENT_QUERY);
    const documentAssistantMedia=window.matchMedia(DOCUMENT_ASSISTANT_PERSISTENT_QUERY);
    const syncCorpusTree=(matches:boolean)=>{
      setCorpusTreePersistent(matches);
      setLeftOpen(matches && localStorage.getItem('cial-kc-left-open')!=='false');
    };
    const syncDocumentAssistant=(matches:boolean)=>{
      setDocumentAssistantPersistent(matches);
      setRightOpen(matches && localStorage.getItem('cial-kc-right-open')!=='false');
    };
    const handleCorpusTreeChange=(event:MediaQueryListEvent)=>syncCorpusTree(event.matches);
    const handleDocumentAssistantChange=(event:MediaQueryListEvent)=>syncDocumentAssistant(event.matches);
    syncCorpusTree(corpusTreeMedia.matches);
    syncDocumentAssistant(documentAssistantMedia.matches);
    corpusTreeMedia.addEventListener('change',handleCorpusTreeChange);
    documentAssistantMedia.addEventListener('change',handleDocumentAssistantChange);
    return ()=>{
      corpusTreeMedia.removeEventListener('change',handleCorpusTreeChange);
      documentAssistantMedia.removeEventListener('change',handleDocumentAssistantChange);
    };
  },[]);
  const toggleCorpusTree=()=>{
    setLeftOpen((current)=>{
      const next=!current;
      localStorage.setItem('cial-kc-left-open',String(next));
      if(next&&!window.matchMedia(CORPUS_TREE_PERSISTENT_QUERY).matches)setRightOpen(false);
      return next;
    });
  };
  const toggleDocumentAssistant=()=>{
    setRightOpen((current)=>{
      const next=!current;
      localStorage.setItem('cial-kc-right-open',String(next));
      if(next&&!window.matchMedia(DOCUMENT_ASSISTANT_PERSISTENT_QUERY).matches)setLeftOpen(false);
      return next;
    });
  };
  const closeCorpusTree=()=>{localStorage.setItem('cial-kc-left-open','false');setLeftOpen(false);};
  const closeDocumentAssistant=()=>{localStorage.setItem('cial-kc-right-open','false');setRightOpen(false);};
  useEffect(()=>{
    const panel=leftOpen&&!corpusTreePersistent
      ? leftPanelRef.current
      : rightOpen&&!documentAssistantPersistent
        ? rightPanelRef.current
        : null;
    if(!panel)return;
    const previousFocus=window.document.activeElement instanceof HTMLElement
      ? window.document.activeElement
      : null;
    window.requestAnimationFrame(()=>panel.querySelector<HTMLButtonElement>('button[aria-label^="Close"]')?.focus());
    const handleKeyDown=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){
        event.preventDefault();
        if(leftOpen&&!corpusTreePersistent)closeCorpusTree();else closeDocumentAssistant();
        return;
      }
      if(event.key!=='Tab')return;
      const focusable=Array.from(panel.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter((element)=>element.getClientRects().length>0);
      const first=focusable[0];
      const last=focusable.at(-1);
      if(!first||!last)return;
      if(event.shiftKey&&window.document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&window.document.activeElement===last){event.preventDefault();first.focus();}
    };
    window.document.addEventListener('keydown',handleKeyDown);
    return()=>{window.document.removeEventListener('keydown',handleKeyDown);previousFocus?.focus();};
  },[corpusTreePersistent,documentAssistantPersistent,leftOpen,rightOpen]);
  useEffect(()=>{localStorage.setItem('cial-kc-left-width',String(leftWidth));},[leftWidth]);
  useEffect(()=>{localStorage.setItem('cial-kc-right-width',String(rightWidth));},[rightWidth]);
  const beginResize=(side:'left'|'right')=>(event:React.PointerEvent)=>{
    if(
      (side==='left'&&!window.matchMedia(CORPUS_TREE_PERSISTENT_QUERY).matches)
      ||(side==='right'&&!window.matchMedia(DOCUMENT_ASSISTANT_PERSISTENT_QUERY).matches)
    )return;
    event.preventDefault();
    const startX=event.clientX;
    const startWidth=side==='left'?leftWidth:rightWidth;
    const onMove=(move:PointerEvent)=>{
      const delta=side==='left'?move.clientX-startX:startX-move.clientX;
      const next=Math.max(side==='left'?240:320,Math.min(side==='left'?400:520,startWidth+delta));
      if(side==='left')setLeftWidth(next);else setRightWidth(next);
    };
    const onUp=()=>{window.removeEventListener('pointermove',onMove);window.removeEventListener('pointerup',onUp);};
    window.addEventListener('pointermove',onMove);window.addEventListener('pointerup',onUp);
  };
  const navigateCitation=(page:number,chunkId?:string|null)=>{setActivePage(page);setRequestedPage(page);setRequestedChunkId(chunkId??null);const params=new URLSearchParams(window.location.search);params.set('page',String(page));if(chunkId)params.set('chunk',chunkId);else params.delete('chunk');window.history.replaceState(null,'',`${window.location.pathname}?${params}`);};

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
        <div className="rounded-xl border border-border bg-card px-5 py-4 text-sm text-muted-foreground shadow-sm">
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
      <header className="mb-2 flex h-14 shrink-0 items-center gap-3 border-b border-popover-border bg-popover/88 pl-14 pr-3 shadow-xs backdrop-blur lg:px-3"><button onClick={toggleCorpusTree} className="ce-icon-button" aria-label="Toggle corpus tree" aria-expanded={leftOpen}><PanelLeftClose size={17}/></button><button onClick={()=>setSearchOpen(true)} className="flex h-10 min-w-0 max-w-xl flex-1 items-center gap-2 rounded-lg border border-border bg-secondary px-3 text-sm text-muted-foreground"><Search size={16}/><span className="truncate">Search Corpus…</span><span className="ml-auto hidden rounded border bg-card px-1.5 py-0.5 text-[10px] sm:inline">Ctrl + K</span></button><button onClick={()=>navigate('/knowledge-center')} className="ce-icon-button hidden sm:inline-flex" aria-label="Upload documents"><Upload size={17}/></button><button onClick={()=>void Promise.all([treeQuery.refetch(),documentQuery.refetch(),previewQuery.refetch()])} className="ce-icon-button hidden sm:inline-flex" aria-label="Refresh workspace"><RefreshCw size={17}/></button><button onClick={toggleDocumentAssistant} className="ce-icon-button" aria-label="Toggle document assistant" aria-expanded={rightOpen}><PanelRightClose size={17}/></button></header>
      <div className="flex min-h-0 flex-1 overflow-hidden">
      {leftOpen&&!corpusTreePersistent?<div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]" aria-hidden="true" onClick={closeCorpusTree} data-testid="corpus-tree-overlay"/>:null}
      {leftOpen&&treeQuery.data?.root?<aside ref={leftPanelRef} className="fixed inset-y-0 left-0 z-50 h-full max-w-[85vw] shrink-0 border-r border-border bg-card shadow-xl xl:relative xl:inset-auto xl:z-auto xl:shadow-none" style={{width:leftWidth}} data-testid="corpus-tree-panel" role={corpusTreePersistent?undefined:'dialog'} aria-modal={corpusTreePersistent?undefined:true} aria-label={corpusTreePersistent?undefined:'Corpus Tree'}><button onClick={closeCorpusTree} className="absolute right-2 top-2 ce-icon-button xl:hidden" aria-label="Close corpus tree"><PanelLeftClose size={16}/></button><CorpusTreePanel root={treeQuery.data.root} selectedDocumentId={documentId}/><div role="separator" aria-label="Resize corpus tree" onPointerDown={beginResize('left')} className="absolute inset-y-0 right-0 hidden w-1 cursor-col-resize bg-transparent hover:bg-primary/25 xl:block"/></aside>:null}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
      <div className="mb-2 flex shrink-0 flex-col gap-2 border-b border-border bg-card/92 px-3 py-2 shadow-xs lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <button type="button" onClick={goBack} className="ce-icon-button h-9 w-9 shrink-0" aria-label="Back to Knowledge Center">
            <ArrowLeft size={18} />
          </button>
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h1 className="safe-text min-w-0 text-base font-semibold text-foreground sm:text-lg">{title}</h1>
              <span className="ce-badge px-2 py-1 text-[11px]">{typeLabel}</span>
              <FileIndexingStatus status={document?.indexing_status || 'pending'} stage={document?.indexing_stage}
                safeMessage={document?.indexing_safe_message} retryAllowed={document?.retry_allowed}
                documentId={document?.id} fileName={document?.name} />
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
              <span>{formatBytes(document?.size_bytes)}</span>
              <span>{effectivePageCount ? `${effectivePageCount} ${preview?.slides?.length ? 'slides' : 'pages'}` : 'Preview workspace'}</span>
              <span>Updated {formatDate(document?.updated_at || document?.modified_at)}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="hidden h-9 min-w-0 items-center gap-2 rounded-md border border-border bg-muted px-3 text-sm text-muted-foreground md:flex">
            <Search size={15} />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search preview"
              className="w-36 bg-transparent text-foreground placeholder:text-muted-foreground"
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
          <button type="button" onClick={() => void useInAssistant()} disabled={!document || unavailable} className="ce-action ce-action-primary h-9 px-3 disabled:opacity-50">
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
          <main className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card">
            {previewQuery.isLoading ? (
              <div className="flex h-full min-h-[28rem] items-center justify-center text-sm text-muted-foreground">Loading preview...</div>
            ) : previewQuery.isError ? (
              <div className="flex h-full min-h-[28rem] items-center justify-center p-6">
                <div className="max-w-lg rounded-xl border border-warning/30 bg-warning/10 p-5 text-center text-sm text-warning-foreground">
                  <AlertTriangle className="mx-auto mb-3" size={28} />
                  <p className="font-semibold">Preview unavailable</p>
                  <p className="mt-2 leading-6">The metadata loaded, but the preview endpoint did not return a usable inline preview. Use Open or Download to inspect the source document.</p>
                </div>
              </div>
            ) : (
              <div className="flex min-h-0 flex-1 flex-col">
                {preview?.preview_notice ? (
                  <div className="border-b border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning-foreground">
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
              </div>
            )}
          </main>
        </div>
      )}
      </div>
      {rightOpen&&!documentAssistantPersistent?<div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]" aria-hidden="true" onClick={closeDocumentAssistant} data-testid="document-assistant-overlay"/>:null}
      {rightOpen&&document?<aside ref={rightPanelRef} className="fixed inset-y-0 right-0 z-50 h-full max-w-[94vw] shrink-0 border-l border-border bg-card shadow-xl lg:relative lg:inset-auto lg:z-auto lg:shadow-none" style={{width:rightWidth}} data-testid="document-assistant-panel" role={documentAssistantPersistent?undefined:'dialog'} aria-modal={documentAssistantPersistent?undefined:true} aria-label={documentAssistantPersistent?undefined:'Document AI Assistant'}><div role="separator" aria-label="Resize document assistant" onPointerDown={beginResize('right')} className="absolute inset-y-0 left-0 hidden w-1 cursor-col-resize bg-transparent hover:bg-primary/25 lg:block"/><button onClick={closeDocumentAssistant} className="absolute right-2 top-2 z-10 ce-icon-button lg:hidden" aria-label="Close document assistant"><PanelRightClose size={16}/></button><DocumentAssistantPanel document={document} preview={preview} onAsk={useInAssistant} onCitation={navigateCitation}/></aside>:null}
      </div>
    </div>
  );
}
