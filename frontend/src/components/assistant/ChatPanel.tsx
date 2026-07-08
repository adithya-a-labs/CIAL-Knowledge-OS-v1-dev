import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Mic, Paperclip, RefreshCcw, Send } from 'lucide-react';
import ChatControlBar from './ChatControlBar';
import ChatMessage, { ChatMessageData } from './ChatMessage';
import ContextChips from './ContextChips';
import ContextManagerDialog from './ContextManagerDialog';
import RetrievalTimeline from './RetrievalTimeline';
import SourceViewerPanel from './SourceViewerPanel';
import { askQuestion, getHealth, uploadDocument } from '@/api/client';
import { toAssistantMessage, toChatRequest } from '@/api/adapters';
import type { HealthResponse } from '@/api/types';
import {
  CONTEXT_DOCUMENTS,
  INITIAL_ASSISTANT_MESSAGES,
  MOCK_CHAT_SOURCES,
  RETRIEVAL_STAGES,
} from '@/data/assistantData';
import { toast } from '@/hooks/use-toast';
import type {
  ChatRequestPayload,
  ChatSource,
  FeedbackType,
  ResponseLength,
  SearchScope,
  UploadedFileContext,
} from '@/types/assistant';

const supportedFileTypes = '.pdf,.docx,.pptx,.xlsx,.csv,.txt,image/*';

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
    uploadStatus: 'mock_uploaded',
  };
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessageData[]>(
    INITIAL_ASSISTANT_MESSAGES as ChatMessageData[]
  );
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [searchScope, setSearchScope] = useState<SearchScope>('hybrid');
  const [responseLength, setResponseLength] = useState<ResponseLength>('detailed');
  const [selectedContextIds, setSelectedContextIds] = useState<string[]>([
    'enterprise-airfield-lighting',
    'enterprise-electrical-sop',
  ]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileContext[]>([]);
  const [contextManagerOpen, setContextManagerOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<ChatSource | null>(null);
  const [sourceViewerOpen, setSourceViewerOpen] = useState(false);
  const [feedbackByMessageId, setFeedbackByMessageId] = useState<Record<string, FeedbackType>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const healthQuery = useQuery({
    queryKey: ['backend-health'],
    queryFn: getHealth,
    retry: false,
    refetchInterval: 5000,
  });
  const chatReady = Boolean(healthQuery.data?.engine_ready);
  const healthLabel = readinessLabel(healthQuery.data);

  const selectedDocuments = useMemo(
    () => CONTEXT_DOCUMENTS.filter((doc) => selectedContextIds.includes(doc.id)),
    [selectedContextIds]
  );

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
    setSelectedSource(source);
    setSourceViewerOpen(true);
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

    const requestPayload: ChatRequestPayload = {
      query: input.trim(),
      searchScope,
      responseLength,
      selectedContextIds,
      uploadedFileIds: uploadedFiles.map((file) => file.id),
    };

    const userMsg: ChatMessageData = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: requestPayload.query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
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
        sources: adapted.sources,
        metadata: adapted.metadata,
        relatedQuestions: adapted.relatedQuestions,
      };

      setMessages((prev) => [...prev, aiMsg]);
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

    const newFiles = Array.from(files).map(createUploadedFileContext);
    setUploadedFiles((current) => [...current, ...newFiles]);
    if (fileInputRef.current) fileInputRef.current.value = '';

    const results = await Promise.allSettled(Array.from(files).map((file) => uploadDocument(file)));
    const failed = results.filter((result) => result.status === 'rejected').length;
    if (failed > 0) {
      toast({
        title: 'Some uploads failed',
        description: `${failed} file${failed === 1 ? '' : 's'} could not be saved to the backend.`,
      });
      return;
    }
    toast({ title: 'Upload saved', description: 'The file was saved under data/files.' });
  };

  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast({ title: 'Copied response' });
    } catch {
      toast({ title: 'Copy failed', description: 'Clipboard permission is unavailable.' });
    }
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 gap-4" data-testid="assistant-workspace">
      <div className="ce-panel responsive-card flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden" data-testid="chat-panel">
        <ChatControlBar
          searchScope={searchScope}
          responseLength={responseLength}
          selectedContextCount={selectedContextIds.length}
          uploadedFileCount={uploadedFiles.length}
          onSearchScopeChange={setSearchScope}
          onResponseLengthChange={setResponseLength}
          onManageContext={() => setContextManagerOpen(true)}
        />
        <div
          className={`border-b px-4 py-2 text-xs ${
            chatReady
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
              : 'border-amber-200 bg-amber-50 text-amber-900'
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

        <div className="scrollbar-soft min-h-0 flex-1 space-y-4 overflow-y-auto bg-[hsl(210_20%_98%)] p-3 sm:space-y-5 sm:p-5" data-testid="chat-messages">
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
                // TODO: Wire assistant actions to backend job endpoints.
                toast({ title: `${label} is coming soon` });
              }}
              onFeedback={(messageId, feedback) =>
                setFeedbackByMessageId((current) => ({ ...current, [messageId]: feedback }))
              }
            />
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <RetrievalTimeline activeStageIndex={activeStageIndex} />
            </div>
          )}
          {errorMessage && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" data-testid="assistant-error">
              {errorMessage}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <ContextChips
          selectedDocuments={selectedDocuments}
          uploadedFiles={uploadedFiles}
          searchScope={searchScope}
          onRemoveDocument={(id) =>
            setSelectedContextIds((current) => current.filter((contextId) => contextId !== id))
          }
          onRemoveFile={(id) =>
            setUploadedFiles((current) => current.filter((file) => file.id !== id))
          }
        />

        <div className="border-t border-border bg-white px-4 py-1.5">
          <p className="text-center text-[10px] text-muted-foreground">
            All responses may be inaccurate. Please verify critical information with official documents.
          </p>
        </div>

        <div className="border-t border-border bg-white p-3 sm:p-4">
          <div className="ce-control flex min-w-0 items-center gap-2 px-3 py-2.5 sm:px-4">
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
              className="ce-icon-button"
              aria-label="Attach files"
              data-testid="button-attach-file"
            >
              <Paperclip size={16} />
            </button>
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) handleSend();
              }}
              placeholder={chatReady ? 'Ask a grounded question...' : 'Backend readiness pending...'}
              className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              data-testid="input-chat"
            />
            <button className="ce-icon-button" data-testid="button-voice" aria-label="Start voice input">
              <Mic size={16} />
            </button>
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || isLoading || !chatReady}
              className="ce-action ce-action-primary h-8 w-8 shrink-0 p-0 disabled:border-gray-300 disabled:bg-gray-300"
              data-testid="button-send"
              aria-label="Send message"
            >
              <Send size={14} />
            </button>
          </div>
        </div>

        <ContextManagerDialog
          open={contextManagerOpen}
          selectedIds={selectedContextIds}
          onApply={setSelectedContextIds}
          onClose={() => setContextManagerOpen(false)}
        />
      </div>

      <SourceViewerPanel
        open={sourceViewerOpen}
        source={selectedSource}
        sources={allVisibleSources.length > 0 ? allVisibleSources : MOCK_CHAT_SOURCES}
        onClose={() => setSourceViewerOpen(false)}
        onSelectSource={openSource}
      />
    </div>
  );
}
