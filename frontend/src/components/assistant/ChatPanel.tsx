import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Paperclip, RefreshCcw, Send } from 'lucide-react';
import { useAssistantSessions } from './AssistantSessionContext';
import ChatControlBar from './ChatControlBar';
import ChatMessage, { ChatMessageData } from './ChatMessage';
import ContextChips from './ContextChips';
import ContextManagerDialog from './ContextManagerDialog';
import RetrievalTimeline from './RetrievalTimeline';
import SourceViewerPanel from './SourceViewerPanel';
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  const openSource = (source: ChatSource) => {
    if (toUuidDocumentId(source.documentId)) {
      setSelectedSource(source);
      setSourceViewerOpen(true);
      return;
    }
    const matchedDocument =
      corpusLookup.documentsById.get(source.documentId) ??
      corpusLookup.documents.find((document) => document.relative_path === source.relativePath || document.relative_path === source.documentId) ??
      corpusLookup.documents.find((document) => document.name === source.documentTitle || source.documentTitle.endsWith(document.name));
    setSelectedSource(
      matchedDocument
        ? {
            ...source,
            documentId: matchedDocument.id,
            relativePath: matchedDocument.relative_path,
            documentTitle: matchedDocument.name,
            fileType: matchedDocument.file_type,
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

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 gap-4 overflow-hidden" data-testid="assistant-workspace">
      <div
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[1.75rem] bg-white shadow-[0_28px_80px_-48px_rgba(15,23,42,0.45)] ring-1 ring-black/5"
        data-testid="chat-panel"
      >
        <div
          className={`border-b px-5 py-3 text-xs ${
            chatReady
              ? 'border-emerald-200 bg-emerald-50/80 text-emerald-800'
              : 'border-amber-200 bg-amber-50/80 text-amber-900'
          }`}
          data-testid="backend-readiness-banner"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>
              <strong>{healthLabel}</strong>
              {healthQuery.data?.message ? `: ${healthQuery.data.message}` : ''}
            </span>
            <button
              type="button"
              onClick={() => healthQuery.refetch()}
              className="inline-flex items-center gap-1 self-start font-medium sm:self-auto"
              data-testid="button-refresh-backend-health"
            >
              <RefreshCcw size={13} />
              Refresh
            </button>
          </div>
        </div>

        <div
          className="scrollbar-soft min-h-0 flex-1 space-y-5 overflow-y-auto bg-[radial-gradient(circle_at_top,#f8fbf5_0%,#f8fafc_40%,#f8fafc_100%)] px-4 py-5 sm:px-6 sm:py-6"
          data-testid="chat-messages"
        >
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
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

          {visibleSuggestedPrompts.length > 0 ? (
            <div className="flex flex-wrap gap-2 px-1">
              {visibleSuggestedPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setInput(prompt)}
                  className="ce-action min-h-8 rounded-full px-3 text-primary"
                >
                  {prompt}
                </button>
              ))}
            </div>
          ) : null}

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
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-border bg-white/96 px-4 pb-4 pt-3 backdrop-blur sm:px-5">
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

          <div className="mt-3 rounded-[1.5rem] border border-border bg-[hsl(0_0%_100%/0.96)] p-3 shadow-[0_12px_34px_-28px_rgba(15,23,42,0.45)]">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
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
              <p className="text-[10px] text-muted-foreground">
                Grounded responses only. Verify critical information with the source documents.
              </p>
            </div>

            <div className="ce-control flex min-w-0 items-end gap-3 rounded-[1.25rem] bg-[hsl(210_20%_98%)] px-3 py-3">
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
                className="ce-icon-button h-10 w-10 rounded-full"
                aria-label="Attach files"
                data-testid="button-attach-file"
              >
                <Paperclip size={16} />
              </button>

              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
                placeholder={chatReady ? 'Ask a grounded question' : 'Backend readiness pending'}
                className="max-h-40 min-h-[3rem] flex-1 resize-none bg-transparent py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
                data-testid="input-chat"
              />

              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!input.trim() || isLoading || !chatReady}
                className="ce-action ce-action-primary h-10 w-10 shrink-0 rounded-full p-0 disabled:border-gray-300 disabled:bg-gray-300"
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

      <SourceViewerPanel
        open={sourceViewerOpen}
        source={selectedSource}
        sources={
          allVisibleSources.length > 0
            ? allVisibleSources.map((source) => ({
                ...source,
                documentId: toUuidDocumentId(source.documentId) ?? source.documentId,
              }))
            : MOCK_CHAT_SOURCES
        }
        onClose={() => setSourceViewerOpen(false)}
        onSelectSource={openSource}
      />
    </div>
  );
}
