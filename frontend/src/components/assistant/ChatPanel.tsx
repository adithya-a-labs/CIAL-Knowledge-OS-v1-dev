import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileText, Paperclip, Send, Sparkles } from 'lucide-react';
import { useAssistantSessions } from './AssistantSessionContext';
import ChatControlBar from './ChatControlBar';
import ChatMessage, { ChatMessageData } from './ChatMessage';
import ContextChips from './ContextChips';
import ContextManagerDialog from './ContextManagerDialog';
import RetrievalTimeline from './RetrievalTimeline';
import SourceViewerPanel from './SourceViewerPanel';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';
import { askQuestion, getCorpusTree, getHealth, uploadDocument } from '@/api/client';
import { flattenCorpusTree, toAssistantMessage, toChatRequest } from '@/api/adapters';
import type { CorpusDocument, HealthResponse, SelectedContextItem } from '@/api/types';
import {
  MOCK_CHAT_SOURCES,
  RETRIEVAL_STAGES,
} from '@/data/assistantData';
import { suggestedPrompts } from '@/data/homePageData';
import { toast } from '@/hooks/use-toast';
import type {
  ChatRequestPayload,
  ChatSource,
  UploadedFileContext,
} from '@/types/assistant';

const supportedFileTypes = '.pdf,.docx,.pptx,.xlsx,.csv,.txt,image/*';
const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_CONTEXT_INTENT_STORAGE_KEY = 'cial-assistant-context-intent';
const ASSISTANT_SOURCE_PANEL_SIZE_STORAGE_KEY = 'cial-assistant-source-panel-size';
const DEFAULT_SOURCE_PANEL_SIZE = 40;

function readinessLabel(healthStatus: HealthResponse | undefined) {
  if (!healthStatus) return 'Backend starting';
  if (healthStatus.engine_ready && healthStatus.status === 'ready') return 'Ready';
  if (healthStatus.status === 'indexing') return 'Indexing documents';
  if (healthStatus.status === 'no_documents') return 'No documents found';
  if (!healthStatus.qdrant_ready) return 'Qdrant unavailable';
  if (!healthStatus.models_ready) return 'Model unavailable';
  if (healthStatus.status === 'failed') return 'Startup failed';
  return 'Backend starting';
}

function createUploadedFileContext(file: File): UploadedFileContext {
  return {
    id: `upload-${Date.now()}-${Math.random().toString(36).slice(2)}-${file.name.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`,
    name: file.name,
    size: file.size,
    type: file.type || file.name.split('.').pop()?.toUpperCase() || 'Unknown',
    sourceType: 'upload',
    uploadStatus: 'uploading',
  };
}

function toUuidDocumentId(value: string | undefined) {
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
    ? value
    : null;
}

function readAssistantSourcePanelSize() {
  if (typeof window === 'undefined') return DEFAULT_SOURCE_PANEL_SIZE;
  const raw = window.localStorage.getItem(ASSISTANT_SOURCE_PANEL_SIZE_STORAGE_KEY);
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) && parsed >= 25 && parsed <= 70 ? parsed : DEFAULT_SOURCE_PANEL_SIZE;
}

function writeAssistantSourcePanelSize(size: number) {
  if (typeof window === 'undefined' || !Number.isFinite(size) || size <= 0) return;
  window.localStorage.setItem(ASSISTANT_SOURCE_PANEL_SIZE_STORAGE_KEY, String(Math.round(size * 100) / 100));
}

function resizeComposerTextarea(textarea: HTMLTextAreaElement | null) {
  if (!textarea) return;
  textarea.style.height = '0px';
  textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
}

export default function ChatPanel() {
  const {
    activeSession,
    updateActiveSession,
  } = useAssistantSessions();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [contextManagerOpen, setContextManagerOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<ChatSource | null>(null);
  const [sourceViewerOpen, setSourceViewerOpen] = useState(false);
  const [isDesktopViewport, setIsDesktopViewport] = useState(() => window.innerWidth >= 1024);
  const [sourcePanelSize, setSourcePanelSize] = useState(readAssistantSourcePanelSize);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement>(null);
  const chatMessagesRef = useRef<HTMLDivElement>(null);
  const [chatMessagesWidth, setChatMessagesWidth] = useState<number>(0);
  const messages = activeSession.messages as ChatMessageData[];
  const selectedContextItems = activeSession.selectedContextItems as SelectedContextItem[];
  const uploadedFiles = activeSession.uploadedFiles as UploadedFileContext[];
  const feedbackByMessageId = activeSession.feedbackByMessageId;
  const searchScope = activeSession.searchScope;
  const activeProfile = activeSession.activeProfile;

  const healthQuery = useQuery({
    queryKey: ['backend-health'],
    queryFn: getHealth,
    retry: false,
    refetchInterval: 5000,
  });
  const corpusTreeQuery = useQuery({
    queryKey: ['corpus-tree-assistant'],
    queryFn: getCorpusTree,
    retry: false,
    staleTime: 30_000,
  });
  const chatReady = Boolean(healthQuery.data?.engine_ready);
  const healthLabel = readinessLabel(healthQuery.data);

  const corpusLookup = useMemo(() => {
    if (!corpusTreeQuery.data?.root) {
      return {
        documentsById: new Map<string, CorpusDocument>(),
        documents: [] as CorpusDocument[],
      };
    }
    const flattened = flattenCorpusTree(corpusTreeQuery.data.root);
    return {
      documentsById: new Map<string, CorpusDocument>(flattened.documents.map((document) => [document.id, document])),
      documents: flattened.documents,
    };
  }, [corpusTreeQuery.data]);

  useEffect(() => {
    window.localStorage.setItem(ASSISTANT_CONTEXT_STORAGE_KEY, JSON.stringify(selectedContextItems));
  }, [selectedContextItems]);

  useEffect(() => {
    try {
      const intent = window.localStorage.getItem(ASSISTANT_CONTEXT_INTENT_STORAGE_KEY);
      if (!intent) return;
      const raw = window.localStorage.getItem(ASSISTANT_CONTEXT_STORAGE_KEY);
      window.localStorage.removeItem(ASSISTANT_CONTEXT_INTENT_STORAGE_KEY);
      if (!raw) return;
      const restored = JSON.parse(raw) as SelectedContextItem[];
      if (Array.isArray(restored) && restored.length > 0) {
        updateActiveSession({ selectedContextItems: restored });
      }
    } catch {
      // Ignore malformed local storage and keep the session unchanged.
    }
  }, [activeSession.id, updateActiveSession]);

  useEffect(() => {
    setInput('');
    setErrorMessage(null);
    setSelectedSource(null);
    setSourceViewerOpen(false);
  }, [activeSession.id]);

  useEffect(() => {
    resizeComposerTextarea(composerTextareaRef.current);
  }, [input, activeSession.id]);

  const allVisibleSources = useMemo(() => {
    const sourceMap = new Map<string, ChatSource>();
    messages.forEach((message) => {
      message.sources?.forEach((source) => sourceMap.set(source.id, source));
    });
    if (selectedSource) sourceMap.set(selectedSource.id, selectedSource);
    return Array.from(sourceMap.values()).sort((a, b) => a.citationIndex - b.citationIndex);
  }, [messages, selectedSource]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, activeStageIndex]);

  useEffect(() => {
    if (!isLoading) {
      setActiveStageIndex(0);
      return;
    }

    const interval = window.setInterval(() => {
      setActiveStageIndex((current) => Math.min(current + 1, RETRIEVAL_STAGES.length - 1));
    }, 220);

    return () => window.clearInterval(interval);
  }, [isLoading]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(min-width: 1024px)');
    const handleViewportChange = () => setIsDesktopViewport(mediaQuery.matches);
    handleViewportChange();
    mediaQuery.addEventListener('change', handleViewportChange);
    return () => mediaQuery.removeEventListener('change', handleViewportChange);
  }, []);

  useEffect(() => {
    const element = chatMessagesRef.current;
    if (!element) return;

    const resizeObserver = new ResizeObserver((entries) => {
      if (entries && entries[0]) {
        setChatMessagesWidth(entries[0].contentRect.width);
      }
    });
    resizeObserver.observe(element);
    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  const openSource = (source: ChatSource) => {
    console.debug('[citation-click]', {
      citationId: source.citationId ?? source.id,
      documentId: source.documentId,
      repositoryId: source.repositoryId,
      extractedPage: source.pageNumber ?? null,
      normalizedPage: source.pageNumber && source.pageNumber > 0 ? Math.trunc(source.pageNumber) : null,
      pdfEndpointUrl: source.fileUrl ?? null,
    });
    if (toUuidDocumentId(source.documentId)) {
      setSelectedSource(source);
      setSourceViewerOpen(true);
      return;
    }
    const matchedDocument =
      corpusLookup.documentsById.get(source.documentId) ??
      corpusLookup.documents.find((document) => document.relative_path === source.relativePath || document.relative_path === source.documentId) ??
      corpusLookup.documents.find((document) => document.name === source.documentTitle || document.relative_path.endsWith(`/${source.documentTitle}`));
    setSelectedSource(
      matchedDocument
        ? {
            ...source,
            documentId: matchedDocument.id,
            relativePath: matchedDocument.relative_path,
            documentTitle: matchedDocument.name,
            fileType: matchedDocument.file_type,
            fileUrl: source.fileUrl ?? `/api/corpus/document/${matchedDocument.id}/file`,
            pageCount: matchedDocument.page_count ?? undefined,
          }
        : source,
    );
    setSourceViewerOpen(true);
  };

  const clearActiveContext = () => {
    updateActiveSession({
      selectedContextItems: [],
      uploadedFiles: [],
    });
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    if (!chatReady) {
      toast({
        title: 'Backend is not ready',
        description: healthQuery.data?.message ?? 'Startup checks are still running.',
      });
      return;
    }

    const explicitDocumentIds = selectedContextItems
        .filter((item) => item.type === 'document')
        .map((item) => item.id);
    const explicitFolderIds = selectedContextItems
        .filter((item) => item.type === 'folder')
        .map((item) => item.id);
    const uploadedDocumentIds = uploadedFiles
        .map((file) => file.backendDocumentId)
        .filter((value): value is string => Boolean(value));

    const requestPayload: ChatRequestPayload = {
      query: input.trim(),
      searchScope,
      activeProfile,
      selectedDocumentIds: [...explicitDocumentIds, ...uploadedDocumentIds],
      selectedFolderIds: explicitFolderIds,
      uploadedFileIds: uploadedDocumentIds,
    };

    const userMsg: ChatMessageData = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: requestPayload.query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    updateActiveSession({
      messages: [...messages, userMsg],
    });
    setInput('');
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await askQuestion(toChatRequest(requestPayload));
      const adapted = toAssistantMessage(response, requestPayload);
      const aiMsg: ChatMessageData = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: adapted.content,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: adapted.citations,
        sources: adapted.sources,
        metadata: adapted.metadata,
        relatedQuestions: adapted.relatedQuestions,
      };

      updateActiveSession({
        messages: [...messages, userMsg, aiMsg],
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'The backend could not answer this question.';
      setErrorMessage(message);
      toast({
        title: 'Assistant request failed',
        description: message,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileChange = async (files: FileList | null) => {
    if (!files?.length) return;

    const queuedFiles = Array.from(files).map(createUploadedFileContext);
    updateActiveSession({
      uploadedFiles: [...uploadedFiles, ...queuedFiles],
    });
    if (fileInputRef.current) fileInputRef.current.value = '';

    const results = await Promise.allSettled(Array.from(files).map((file) => uploadDocument(file)));
    updateActiveSession({
      uploadedFiles: [...uploadedFiles, ...queuedFiles].map((file) => {
        const resultIndex = queuedFiles.findIndex((queuedFile) => queuedFile.id === file.id);
        if (resultIndex === -1) return file;
        const result = results[resultIndex];
        if (result.status === 'fulfilled') {
          return {
            ...file,
            uploadStatus: 'uploaded',
            backendDocumentId: result.value.id,
          };
        }
        return {
          ...file,
          uploadStatus: 'upload_failed',
        };
      }),
    });

    const failed = results.filter((result) => result.status === 'rejected').length;
    if (failed > 0) {
      toast({
        title: 'Some uploads failed',
        description: `${failed} file${failed === 1 ? '' : 's'} could not be saved to the backend.`,
      });
      return;
    }
    toast({ title: 'Upload saved', description: 'The file is now available to scoped retrieval.' });
  };

  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast({ title: 'Copied response' });
    } catch {
      toast({ title: 'Copy failed', description: 'Clipboard permission is unavailable.' });
    }
  };

  const visibleSuggestedPrompts =
      input.trim().length === 0 && !isLoading ? suggestedPrompts.slice(0, 5) : [];
  const hasSelectedSource = Boolean(selectedSource);
  const showSourceReopen = hasSelectedSource && !sourceViewerOpen;
  const showDesktopSourcePane = hasSelectedSource && sourceViewerOpen && isDesktopViewport;
  const sourceViewerSources =
      allVisibleSources.length > 0
          ? allVisibleSources.map((source) => ({
            ...source,
            documentId: toUuidDocumentId(source.documentId) ?? source.documentId,
          }))
          : MOCK_CHAT_SOURCES;
  const chatWorkspace = (
      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden" data-testid="chat-panel">
        <div
            ref={chatMessagesRef}
            className="scrollbar-soft min-h-0 flex-1 overflow-y-auto bg-[linear-gradient(180deg,#fbfcfa_0%,#ffffff_16rem)] px-3 py-4 sm:px-4 xl:px-5"
            data-testid="chat-messages"
        >
          {messages.length === 0 ? (
              <div className="mx-auto flex h-full min-h-[36vh] max-w-2xl flex-col items-center justify-center px-4 py-10 text-center">
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-[#25611f]/10 text-[#25611f]">
                  <Sparkles size={22} className="animate-pulse" />
                </div>
                <h2 className="text-xl font-semibold tracking-tight text-slate-900">How can I help you today?</h2>
                <p className="mb-6 mt-2 text-sm text-slate-500">
                  Ask questions, scope knowledge, or analyze files in this grounded workspace.
                </p>
                {visibleSuggestedPrompts.length > 0 && (
                    <div className="flex flex-wrap justify-center gap-2">
                      {visibleSuggestedPrompts.map((prompt) => (
                          <button
                              key={prompt}
                              type="button"
                              onClick={() => setInput(prompt)}
                              className="inline-flex min-h-9 items-center rounded-md border border-[#dce4d8] bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5] hover:border-slate-300"
                          >
                            {prompt}
                          </button>
                      ))}
                    </div>
                )}
              </div>
          ) : (
              <div className="space-y-5">
                {messages.map((msg) => (
                    <ChatMessage
                        key={msg.id}
                        message={msg}
                        chatWidth={chatMessagesWidth}
                        selectedFeedback={feedbackByMessageId[msg.id]}
                        onCitationClick={openSource}
                        onSourceOpen={openSource}
                        onRelatedQuestionClick={setInput}
                        onCopy={handleCopy}
                        onUnavailableAction={(label) => {
                          toast({ title: `${label} is coming soon` });
                        }}
                        onFeedback={(messageId, feedback) =>
                            updateActiveSession({
                              feedbackByMessageId: {
                                ...feedbackByMessageId,
                                [messageId]: feedback,
                              },
                            })
                        }
                    />
                ))}

            {isLoading && (
              <div className="flex justify-start">
                <RetrievalTimeline activeStageIndex={activeStageIndex} />
              </div>
            )}

            {errorMessage && (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" data-testid="assistant-error">
                {errorMessage}
              </div>
            )}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-[#e3e9e1] bg-white">
        <div className="flex flex-wrap items-center gap-1.5 border-b border-[#eef2eb] px-3 py-1.5 sm:px-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <ChatControlBar
              searchScope={searchScope}
              activeProfile={activeProfile}
              selectedContextCount={selectedContextItems.length}
              uploadedFileCount={uploadedFiles.length}
              onSearchScopeChange={(value) => updateActiveSession({ searchScope: value })}
              onActiveProfileChange={(value) => updateActiveSession({ activeProfile: value })}
              onManageContext={() => setContextManagerOpen(true)}
              onClearContext={clearActiveContext}
            />

            {showSourceReopen && (
              <button
                type="button"
                onClick={() => setSourceViewerOpen(true)}
                className="inline-flex h-7 items-center gap-1.5 rounded-md border border-[#d8e5ef] bg-[#f5fafe] px-2 text-[11px] font-medium text-[#346c96] transition hover:bg-[#eef6fc]"
                data-testid="button-reopen-source-panel"
              >
                <FileText size={13} />
                Source
              </button>
            )}

            <div
              className="inline-flex h-7 items-center gap-1.5 rounded-md px-1.5 text-[11px] font-medium text-slate-500"
              data-testid="backend-status-chip"
              title={chatReady ? 'Connected' : healthLabel}
              aria-label={chatReady ? 'Connected' : healthLabel}
            >
              <span className={`h-2 w-2 rounded-full ${chatReady ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              <span className="hidden sm:inline">{chatReady ? 'Ready' : healthLabel}</span>
            </div>
          </div>
        </div>

        <ContextChips
          selectedContextItems={selectedContextItems}
          uploadedFiles={uploadedFiles}
          searchScope={searchScope}
          onRemoveContext={(id) =>
            updateActiveSession({
              selectedContextItems: selectedContextItems.filter((context) => context.id !== id),
            })
          }
          onRemoveFile={(id) =>
            updateActiveSession({
              uploadedFiles: uploadedFiles.filter((file) => file.id !== id),
            })
          }
          onClearAll={clearActiveContext}
        />

        <div className="border-t border-[#f0f3ee] px-3 py-1.5 text-[11px] leading-5 text-slate-500 sm:px-4">
          CIAL Knowledge OS uses AI to assist with enterprise knowledge. Responses may contain mistakes. Verify critical information against the cited source documents.
        </div>

        <div className="flex min-w-0 items-end gap-1.5 px-3 py-2 sm:px-4">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={supportedFileTypes}
            className="hidden"
            onChange={(event) => handleFileChange(event.target.files)}
            data-testid="input-file-upload"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[#dce4d8] bg-[#f7faf5] text-slate-600 transition hover:bg-[#eef5e8] hover:text-primary"
            aria-label="Attach files"
            data-testid="button-attach-file"
          >
            <Paperclip size={14} />
          </button>

          <div className="flex min-w-0 flex-1 items-end gap-1.5 rounded-md border border-[#dce4d8] bg-[#fbfcfa] px-2.5 py-1.5">
            <textarea
              ref={composerTextareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
              rows={1}
              placeholder={chatReady ? 'Ask a grounded question' : 'Backend readiness pending'}
              className="max-h-40 min-h-[1.5rem] flex-1 resize-none overflow-y-auto bg-transparent py-0.5 text-sm leading-5 text-foreground outline-none placeholder:text-muted-foreground"
              data-testid="input-chat"
            />

            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={!input.trim() || isLoading || !chatReady}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground transition hover:opacity-95 disabled:bg-gray-300"
              data-testid="button-send"
              aria-label="Send message"
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      </div>

      <ContextManagerDialog
        open={contextManagerOpen}
        selectedItems={selectedContextItems}
        onApply={(items) => updateActiveSession({ selectedContextItems: items })}
        onClose={() => setContextManagerOpen(false)}
      />
    </div>
  );

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 overflow-hidden bg-white" data-testid="assistant-workspace">
      {showDesktopSourcePane ? (
        <ResizablePanelGroup direction="horizontal" className="animate-in fade-in duration-200">
          <ResizablePanel
            defaultSize={100 - sourcePanelSize}
            minSize={30}
            order={1}
            className="flex h-full min-h-0 min-w-0 flex-col transition-[flex-grow] duration-200 ease-out"
            id="chat-panel-resizable"
          >
            {chatWorkspace}
          </ResizablePanel>
          <ResizableHandle className="w-px bg-[#e3e9e1] after:hidden animate-in fade-in duration-200" />
          <ResizablePanel
            defaultSize={sourcePanelSize}
            minSize={25}
            maxSize={70}
            order={2}
            onResize={(size) => {
              if (size <= 0) return;
              setSourcePanelSize(size);
              writeAssistantSourcePanelSize(size);
            }}
            className="flex h-full min-h-0 min-w-0 flex-col animate-in slide-in-from-right-3 fade-in duration-200"
            id="source-viewer-resizable"
          >
            <SourceViewerPanel
              open={sourceViewerOpen}
              source={selectedSource}
              sources={sourceViewerSources}
              onClose={() => setSourceViewerOpen(false)}
              onSelectSource={openSource}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      ) : (
        <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col animate-in fade-in duration-150">
          {chatWorkspace}
        </div>
      )}

      {sourceViewerOpen && !isDesktopViewport && (
        <SourceViewerPanel
          open={sourceViewerOpen}
          source={selectedSource}
          sources={sourceViewerSources}
          onClose={() => setSourceViewerOpen(false)}
          onSelectSource={openSource}
        />
      )}
    </div>
  );
}
