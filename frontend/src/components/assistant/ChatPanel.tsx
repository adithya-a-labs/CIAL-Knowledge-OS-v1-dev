import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bot, Paperclip, RefreshCw, Send } from 'lucide-react';
import { ApiError } from '@/api/types';
import { useAssistantSessions } from './AssistantSessionContext';
import ChatControlBar from './ChatControlBar';
import ChatMessage, { ChatMessageData } from './ChatMessage';
import ContextChips from './ContextChips';
import ContextManagerDialog from './ContextManagerDialog';
import RetrievalTimeline from './RetrievalTimeline';
import SourceViewerPanel from './SourceViewerPanel';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';
import { AUTH_INVALIDATED_EVENT, createAssistantExport, getCorpusTree, regenerateMessage, streamQuestion, toggleMessageFeedback, transformMessage, uploadChatAttachment } from '@/api/client';
import type { AssistantExportFormat, GenerationEvent } from '@/api/types';
import ExportPreviewDialog from './ExportPreviewDialog';
import { flattenCorpusTree, toAssistantMessage, toChatRequest } from '@/api/adapters';
import type { CorpusDocument, SelectedContextItem } from '@/api/types';
import { DEFAULT_RESPONSE_LENGTH, DEFAULT_SEARCH_SCOPE } from '@/data/assistantData';
import { suggestedPrompts } from '@/data/homePageData';
import { toast } from '@/hooks/use-toast';
import type {
  ChatRequestPayload,
  ChatSource,
  UploadedFileContext,
} from '@/types/assistant';
import { useDocumentIndexingStatuses } from '@/hooks/useDocumentIndexingStatuses';
import { useSystemStatus } from '@/hooks/useSystemStatus';
import { AIComposerFrame } from './AIComposer';
import SaveToKnowledgeDialog from './SaveToKnowledgeDialog';
import { isAssistantDraftId } from '@/lib/assistantNavigation';

const supportedFileTypes = '.pdf,.docx,.pptx,.xlsx,.csv,.txt,image/*';
const ASSISTANT_SOURCE_PANEL_SIZE_STORAGE_KEY = 'cial-assistant-source-panel-size';
const DEFAULT_SOURCE_PANEL_SIZE = 40;

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

interface LiveRequestRuntime {
  id: string;
  sessionId: string;
  question: string;
  payload: ChatRequestPayload;
  controller: AbortController;
  startedAt: number;
  userMessage: ChatMessageData;
  placeholder: ChatMessageData;
  events: GenerationEvent[];
  streamedText: string;
  tokenBuffer: string;
  tokenFrame: number | null;
  degraded: { stage: string; reason: string } | null;
}

export default function ChatPanel({ contextLocked = false }: { contextLocked?: boolean } = {}) {
  const {
    activeSession,
    updateActiveSession,
    updateSession,
    appendMessage,
    updateMessage,
    removeRequestMessages,
    promoteDraftSession,
    pendingComposer,
    consumePendingComposer,
  } = useAssistantSessions();
  const [input, setInput] = useState('');
  const [requestClock, setRequestClock] = useState(0);
  const [actionByMessage, setActionByMessage] = useState<Record<string, string>>({});
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [saveKnowledgeMessage,setSaveKnowledgeMessage]=useState<ChatMessageData|null>(null);
  const [activeExportId, setActiveExportId] = useState<string | null>(null);
  const exportSourceRef = useRef<{ sessionId: string; messageId: string; title: string } | null>(null);
  const actionGenerationRef = useRef<Record<string, number>>({});
  const [contextManagerOpen, setContextManagerOpen] = useState(false);
  const [includeSourceExcerpts, setIncludeSourceExcerpts] = useState(true);
  const [showRetrievalDetails, setShowRetrievalDetails] = useState(true);
  const [selectedSource, setSelectedSource] = useState<ChatSource | null>(null);
  const [sourceViewerOpen, setSourceViewerOpen] = useState(false);
  const [isDesktopViewport, setIsDesktopViewport] = useState(() => window.innerWidth >= 1024);
  const [sourcePanelSize, setSourcePanelSize] = useState(readAssistantSourcePanelSize);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement>(null);
  const requestRuntimesRef = useRef(new Map<string, LiveRequestRuntime>());
  const chatMessagesRef = useRef<HTMLDivElement>(null);
  const [chatMessagesWidth, setChatMessagesWidth] = useState<number>(0);
  const messages = activeSession.messages as ChatMessageData[];
  const isLoading = messages.some((message) => message.requestStatus === 'queued' || message.requestStatus === 'running');
  const selectedContextItems = activeSession.selectedContextItems as SelectedContextItem[];
  const uploadedFiles = activeSession.uploadedFiles as UploadedFileContext[];
  const uploadedDocumentIdsForStatus = useMemo(() => uploadedFiles.map((file) => file.backendDocumentId).filter((value): value is string => Boolean(value)), [uploadedFiles]);
  const attachmentStatusQuery = useDocumentIndexingStatuses(uploadedDocumentIdsForStatus);
  const effectiveUploadedFiles = useMemo(() => uploadedFiles.map((file) => {
    const status = file.backendDocumentId ? attachmentStatusQuery.data?.[file.backendDocumentId] : undefined;
    return status ? { ...file, indexingStatus: status.indexing_status, indexingStage: status.indexing_stage || undefined,
      indexingSafeMessage: status.indexing_safe_message || undefined, indexingErrorCode: status.indexing_error_code || undefined,
      retryAllowed: status.retry_allowed } : file;
  }), [attachmentStatusQuery.data, uploadedFiles]);
  const blockingAttachments = effectiveUploadedFiles.filter((file) => file.uploadStatus !== 'uploaded' || file.indexingStatus !== 'indexed');
  const feedbackByMessageId = activeSession.feedbackByMessageId;
  const searchScope = activeSession.searchScope;
  const activeProfile = activeSession.activeProfile;

  const systemStatusQuery = useSystemStatus();
  const corpusTreeQuery = useQuery({
    queryKey: ['corpus-tree-assistant'],
    queryFn: getCorpusTree,
    retry: false,
    staleTime: 30_000,
  });
  const chatReady = Boolean(systemStatusQuery.data?.chat_available);
  const healthLabel = systemStatusQuery.data?.label ?? 'Checking system status';
  const backgroundIndexing = systemStatusQuery.data?.indexing.queue_depth ?? 0;

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
    setInput('');
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
  }, [messages, isLoading, requestClock]);

  useEffect(() => {
    if (!requestRuntimesRef.current.size) return;
    const interval = window.setInterval(() => setRequestClock((value) => value + 1), 1000);
    return () => window.clearInterval(interval);
  }, [isLoading]);

  const stopGenerating = (requestId: string) => {
    const controller = requestRuntimesRef.current.get(requestId)?.controller;
    if (!controller || controller.signal.aborted) return;
    console.debug('[chat-request]', { requestId, status: 'cancelled_by_user' });
    controller.abort();
  };

  useEffect(() => {
    const abortAll = () => {
      requestRuntimesRef.current.forEach((runtime) => {
        runtime.controller.abort();
        if (runtime.tokenFrame !== null) cancelAnimationFrame(runtime.tokenFrame);
        removeRequestMessages(runtime.sessionId, runtime.id);
      });
      requestRuntimesRef.current.clear();
    };
    window.addEventListener(AUTH_INVALIDATED_EVENT, abortAll);
    return () => {
      window.removeEventListener(AUTH_INVALIDATED_EVENT, abortAll);
      abortAll();
    };
  }, [removeRequestMessages]);

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
      normalizedPage: typeof source.pageNumber === 'number' && source.pageNumber > 0
        ? Math.trunc(source.pageNumber)
        : typeof source.pageIndex === 'number' && source.pageIndex >= 0
          ? Math.trunc(source.pageIndex) + 1
          : null,
      pdfEndpointUrl: source.fileUrl ?? null,
    });
    if (source.sourceType === 'note' || source.noteId) {
      const noteId = source.noteId ?? source.documentId;
      if (!noteId) return;
      const params = new URLSearchParams({ tab: 'notes', note: noteId });
      if (source.noteRevision) params.set('revision', String(source.noteRevision));
      if (source.blockId) params.set('citation', source.blockId);
      window.location.assign(`/workspace?${params.toString()}`);
      return;
    }
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
    if(activeSession.contextScope==='selected_documents'||activeSession.contextScope==='selected_context'){
      toast({title:'Context is pinned',description:'This dedicated conversation remains scoped to its authorized source context.'});return;
    }
    updateActiveSession({
      selectedContextItems: [],
      uploadedFiles: [],
    });
  };

  const handleSend = async (
    questionOverride?: string,
    profileOverride?: typeof activeProfile,
    capturedPayload?: ChatRequestPayload,
  ) => {
    const question = (questionOverride ?? input).trim();
    if (!question) return;
    if (blockingAttachments.length > 0) {
      const preparing = blockingAttachments.filter((file) => file.uploadStatus === 'uploading' || ['pending', 'indexing', undefined].includes(file.indexingStatus));
      toast({ title: preparing.length ? 'Preparing attached files' : 'An attached file is not ready',
        description: blockingAttachments.map((file) => file.name).join(', ') });
      return;
    }

    const explicitDocumentIds = selectedContextItems
        .filter((item) => item.type === 'document')
        .map((item) => item.id);
    const explicitFolderIds = selectedContextItems
        .filter((item) => item.type === 'folder')
        .map((item) => item.id);
    const explicitNoteIds = selectedContextItems
        .filter((item) => item.type === 'note')
        .map((item) => item.id);
    const uploadedDocumentIds = effectiveUploadedFiles
        .map((file) => file.backendDocumentId)
        .filter((value): value is string => Boolean(value));

    const requestSessionId = activeSession.id;
    const backendSessionId = activeSession.requestSessionId;
    const requestPayload: ChatRequestPayload = capturedPayload ?? {
      query: question,
      searchScope,
      activeProfile: profileOverride ?? activeProfile,
      selectedDocumentIds: [...explicitDocumentIds, ...uploadedDocumentIds],
      selectedFolderIds: explicitFolderIds,
      selectedNoteIds: explicitNoteIds,
      uploadedFileIds: uploadedDocumentIds,
    };

    const userMsg: ChatMessageData = {
      id: `user-${crypto.randomUUID()}`,
      role: 'user',
      content: requestPayload.query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    const controller = new AbortController();
    const requestId = crypto.randomUUID();
    const placeholder: ChatMessageData = {
      id: `assistant-${requestId}`,
      role: 'assistant',
      content: 'Waiting for assistant capacity…',
      timestamp: 'Queued',
      clientRequestId: requestId,
      requestStatus: 'queued',
      requestEvents: [],
      retryPayload: requestPayload,
    };
    const startedAt = performance.now();
    let requestOutcome: 'completed' | 'cancelled' | 'failed' = 'failed';
    const runtime: LiveRequestRuntime = {
      id: requestId,
      sessionId: requestSessionId,
      question,
      payload: requestPayload,
      controller,
      startedAt,
      userMessage: userMsg,
      placeholder,
      events: [],
      streamedText: '',
      tokenBuffer: '',
      tokenFrame: null,
      degraded: null,
    };
    requestRuntimesRef.current.set(requestId, runtime);
    appendMessage(requestSessionId, userMsg);
    appendMessage(requestSessionId, placeholder);
    if (!questionOverride) setInput('');
    setRequestClock((value) => value + 1);
    console.debug('[chat-request]', { requestId, status: 'started' });

    const updatePlaceholder = (update: Partial<ChatMessageData>) => {
      runtime.placeholder = { ...runtime.placeholder, ...update };
      updateMessage(runtime.sessionId, `assistant-${runtime.id}`, runtime.placeholder);
    };

    try {
      const liveStatus = await systemStatusQuery.refetch();
      if (liveStatus.error || !liveStatus.data) {
        throw new TypeError('The live system status check could not be completed.');
      }
      if (!liveStatus.data.chat_available) {
        throw new ApiError(
          `${liveStatus.data.label}. The assistant cannot start this request yet.`,
          503,
          liveStatus.data,
        );
      }
      const response = await streamQuestion(toChatRequest(
        requestPayload,
        backendSessionId,
        requestId,
      ), (event) => {
        if (event.type === 'stage') {
          runtime.events = [...runtime.events, event].slice(-30);
          const errorState = event.metrics?.error_state;
          if (errorState) {
            runtime.degraded = {
              stage: event.stage_id,
              reason: String(errorState),
            };
          }
          updatePlaceholder({
            requestStatus: event.stage_id === 'queued' ? 'queued' : 'running',
            requestEvents: runtime.events,
            timestamp: event.stage_id.replaceAll('_', ' '),
          });
        }
        if (event.type === 'token' && event.delta && !controller.signal.aborted) {
          runtime.tokenBuffer += event.delta;
          if (runtime.tokenFrame === null) {
            runtime.tokenFrame = requestAnimationFrame(() => {
              runtime.streamedText += runtime.tokenBuffer;
              runtime.tokenBuffer = '';
              runtime.tokenFrame = null;
              updatePlaceholder({
                content: runtime.streamedText,
                requestStatus: 'running',
                timestamp: 'Generating…',
              });
            });
          }
        }
      }, controller.signal, () => {
        runtime.events = [{
          request_id: requestId,
          type: 'stage',
          stage_id: 'connection',
          status: 'completed',
          elapsed_ms: Math.round(performance.now() - startedAt),
          metrics: {},
        }];
        updatePlaceholder({
          requestStatus: 'running',
          requestEvents: runtime.events,
          timestamp: 'Connected',
        });
      });
      if (runtime.tokenFrame !== null) cancelAnimationFrame(runtime.tokenFrame);
      runtime.tokenFrame = null;
      runtime.tokenBuffer = '';
      const adapted = toAssistantMessage(response, requestPayload);
      const persistedUserMsg = response.user_message_id ? { ...userMsg, id: response.user_message_id } : userMsg;
      const aiMsg: ChatMessageData = {
        id: response.assistant_message_id ?? `ai-${Date.now()}`,
        role: 'assistant',
        content: adapted.content,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: adapted.citations,
        sources: adapted.sources,
        metadata: adapted.metadata,
        relatedQuestions: adapted.relatedQuestions,
        clientRequestId: requestId,
        requestStatus: 'completed',
      };

      updateMessage(requestSessionId, userMsg.id, persistedUserMsg);
      updateMessage(requestSessionId, placeholder.id, aiMsg);
      if (isAssistantDraftId(requestSessionId)) {
        if (!response.session_id) throw new Error('The new conversation did not return a session ID.');
        promoteDraftSession(requestSessionId, response.session_id, {});
      }
      const failed = runtime.degraded;
      if (failed) {
        toast({
          title: 'Retrieval completed with degradation',
          description: `${failed.stage.replaceAll('_', ' ')}: ${failed.reason}`,
        });
      }
      requestOutcome = 'completed';
    } catch (error) {
      const cancelled = controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError');
      requestOutcome = cancelled ? 'cancelled' : 'failed';
      if (runtime.tokenFrame !== null) {
        cancelAnimationFrame(runtime.tokenFrame);
        runtime.tokenFrame = null;
      }
      runtime.streamedText += runtime.tokenBuffer;
      runtime.tokenBuffer = '';
      const message = cancelled
        ? 'Generation stopped.'
        : error instanceof Error && error.name === 'TimeoutError'
          ? 'The assistant timed out. Your current index is still available; retry the request.'
        : error instanceof ApiError && error.status === 503
          ? error.message
          : error instanceof TypeError
            ? 'The connection to the local knowledge service was interrupted.'
            : error instanceof Error && error.message
              ? error.message
              : 'The assistant could not complete this request.';
      if (error instanceof ApiError && error.status === 429 && !questionOverride) {
        setInput((current) => current.trim() ? current : question);
      }
      updatePlaceholder({
        content: runtime.streamedText || message,
        requestStatus: cancelled ? 'cancelled' : 'failed',
        requestError: message,
        timestamp: cancelled ? 'Stopped' : 'Failed',
        retryPayload: requestPayload,
      });
      toast({
        title: cancelled ? 'Generation stopped' : 'Assistant request failed',
        description: message,
      });
    } finally {
      if (runtime.tokenFrame !== null) cancelAnimationFrame(runtime.tokenFrame);
      runtime.tokenFrame = null;
      runtime.tokenBuffer = '';
      console.debug('[chat-request]', {
        requestId,
        status: requestOutcome,
        elapsedSeconds: Math.round((performance.now() - startedAt) / 1000),
      });
      requestRuntimesRef.current.delete(requestId);
      setRequestClock((value) => value + 1);
    }
  };

  useEffect(() => {
    if (!pendingComposer) return;
    if (!pendingComposer.autoSubmit) {
      setInput(pendingComposer.question);
      consumePendingComposer();
      return;
    }
    if (!chatReady) return;
    const pending = pendingComposer;
    consumePendingComposer();
    void handleSend(pending.question, pending.profile);
  }, [chatReady, consumePendingComposer, pendingComposer]);

  const handleFileChange = async (files: FileList | null) => {
    if (!files?.length) return;

    const queuedFiles = Array.from(files).map(createUploadedFileContext);
    updateActiveSession({
      uploadedFiles: [...uploadedFiles, ...queuedFiles],
    });
    if (fileInputRef.current) fileInputRef.current.value = '';

    const attachmentSessionId = isAssistantDraftId(activeSession.id) ? undefined : activeSession.id;
    const results = await Promise.allSettled(Array.from(files).map((file) => uploadChatAttachment(file, attachmentSessionId)));
    updateActiveSession({
      uploadedFiles: [...uploadedFiles, ...queuedFiles].map((file) => {
        const resultIndex = queuedFiles.findIndex((queuedFile) => queuedFile.id === file.id);
        if (resultIndex === -1) return file;
        const result = results[resultIndex];
        if (result.status === 'fulfilled') {
          return {
            ...file,
            uploadStatus: 'uploaded',
            backendDocumentId: result.value.document_id,
            backendDocumentVersionId: result.value.document_version_id,
            indexingStatus: result.value.indexing_status,
            indexingSafeMessage: result.value.indexing_safe_message || undefined,
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
    toast({ title: 'Upload saved', description: 'The file is being prepared for grounded retrieval.' });
  };

  const copyResponse = async (message: ChatMessageData) => {
    try {
      await navigator.clipboard.writeText(message.content);
      setActionByMessage((current) => ({ ...current, [message.id]: 'copied' }));
      window.setTimeout(() => setActionByMessage((current) => { const next = { ...current }; delete next[message.id]; return next; }), 1400);
    } catch { toast({ title: 'Copy failed', description: 'Clipboard permission is unavailable.' }); }
  };

  const responseFromRecord = (record: Awaited<ReturnType<typeof transformMessage>>): ChatMessageData => {
    const payload = { answer: record.content, citations: record.citations as never[], sources: record.sources as never[], metadata: record.metadata as never };
    const requestPayload: ChatRequestPayload = { query: '', searchScope, activeProfile, selectedDocumentIds: [], selectedFolderIds: [], selectedNoteIds: [], uploadedFileIds: [] };
    const adapted = toAssistantMessage(payload, requestPayload);
    return { id: record.id, role: 'assistant', content: adapted.content, citations: adapted.citations, sources: adapted.sources, metadata: adapted.metadata, timestamp: new Date(record.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
  };

  const handleResponseAction = async (message: ChatMessageData, action: 'regenerate' | 'explain_simpler' | 'create_checklist' | 'export_pdf' | 'export_docx' | 'copy_formatted' | 'export_markdown' | 'save_knowledge') => {
    if(action==='save_knowledge'){setSaveKnowledgeMessage(message);return;}
    if (action === 'copy_formatted') return void copyResponse(message);
    if (action === 'export_markdown') {
      const blob = new Blob([message.content], { type: 'text/markdown;charset=utf-8' }); const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `cial-response-${message.id.slice(0, 8)}.md`; anchor.click(); URL.revokeObjectURL(url); return;
    }
    const generation = (actionGenerationRef.current[message.id] ?? 0) + 1; actionGenerationRef.current[message.id] = generation;
    const actionSessionId = activeSession.id;
    setActionByMessage((current) => ({ ...current, [message.id]: action }));
    try {
      if (action === 'export_pdf' || action === 'export_docx') {
        if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(message.id)) throw new Error('This response has not been persisted and cannot be exported yet.');
        const title = activeSession.title || 'Assistant Response';
        exportSourceRef.current = { sessionId: actionSessionId, messageId: message.id, title };
        const result = await createAssistantExport({ format: action === 'export_pdf' ? 'pdf' : 'docx', session_id: actionSessionId, message_id: message.id, title });
        setActiveExportId(result.export_id); setExportDialogOpen(true); return;
      }
      if (action === 'regenerate') {
        const response = await regenerateMessage(message.id);
        if (actionGenerationRef.current[message.id] !== generation) return;
        const adapted = toAssistantMessage(response, { query: '', searchScope: message.metadata?.searchScope ?? searchScope, activeProfile: message.metadata?.activeProfile ?? activeProfile, selectedDocumentIds: [], selectedFolderIds: [], selectedNoteIds: [], uploadedFileIds: [] });
        const regenerated: ChatMessageData = { id: response.assistant_message_id ?? crypto.randomUUID(), role: 'assistant', content: adapted.content, citations: adapted.citations, sources: adapted.sources, metadata: adapted.metadata, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
        appendMessage(actionSessionId, regenerated);
      } else {
        const record = await transformMessage(message.id, action);
        if (actionGenerationRef.current[message.id] !== generation) return;
        appendMessage(actionSessionId, responseFromRecord(record));
      }
    } catch (error) { toast({ title: 'Response action failed', description: error instanceof Error ? error.message : 'Please retry this action.' }); }
    finally { if (actionGenerationRef.current[message.id] === generation) setActionByMessage((current) => { const next = { ...current }; delete next[message.id]; return next; }); }
  };
  const regenerateExport = async (format: AssistantExportFormat) => {
    const source = exportSourceRef.current; if (!source) return;
    try { const result = await createAssistantExport({ format, session_id: source.sessionId, message_id: source.messageId, title: source.title }); setActiveExportId(result.export_id); setExportDialogOpen(true); }
    catch (error) { toast({ title: 'Export could not be started', description: error instanceof Error ? error.message : 'Please retry.' }); }
  };

  const handleFeedback = async (messageId: string, feedback: import('@/types/assistant').FeedbackType) => {
    const previous = feedbackByMessageId[messageId] ?? [];
    let optimistic = previous.includes(feedback) ? previous.filter((x) => x !== feedback) : [...previous, feedback];
    if (feedback === 'helpful') optimistic = optimistic.filter((x) => x !== 'not_helpful');
    if (feedback === 'not_helpful') optimistic = optimistic.filter((x) => x !== 'helpful');
    updateActiveSession({ feedbackByMessageId: { ...feedbackByMessageId, [messageId]: optimistic } });
    try { const result = await toggleMessageFeedback(messageId, feedback); updateActiveSession({ feedbackByMessageId: { ...feedbackByMessageId, [messageId]: result.active as import('@/types/assistant').FeedbackType[] } }); }
    catch (error) { updateActiveSession({ feedbackByMessageId: { ...feedbackByMessageId, [messageId]: previous } }); toast({ title: 'Feedback was not saved', description: error instanceof Error ? error.message : 'Please retry.' }); }
  };

  const visibleSuggestedPrompts =
      input.trim().length === 0 ? suggestedPrompts.slice(0, 5) : [];
  const hasSelectedSource = Boolean(selectedSource);
  const showDesktopSourcePane = hasSelectedSource && sourceViewerOpen && isDesktopViewport;
  const sourceViewerSources = allVisibleSources.map((source) => ({
            ...source,
            documentId: toUuidDocumentId(source.documentId) ?? source.documentId,
          }));
  const chatWorkspace = (
      <div className="relative flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden" data-testid="chat-panel">
        <div
            ref={chatMessagesRef}
            className="scrollbar-soft min-h-0 flex-1 overflow-y-auto bg-transparent px-3 pb-44 pt-4 sm:px-4 xl:px-5"
            data-testid="chat-messages"
        >
          {messages.length === 0 ? (
              <div className="mx-auto flex h-full min-h-[36vh] max-w-2xl flex-col items-center justify-center px-4 py-10 text-center">
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Bot size={22} />
                </div>
                <h2 className="text-xl font-semibold tracking-tight text-foreground">How can I help you today?</h2>
                <p className="mb-6 mt-2 text-sm text-muted-foreground">
                  Ask questions, scope knowledge, or analyze files in this grounded workspace.
                </p>
                {visibleSuggestedPrompts.length > 0 && (
                    <div className="flex flex-wrap justify-center gap-2">
                      {visibleSuggestedPrompts.map((prompt) => (
                          <button
                              key={prompt}
                              type="button"
                              onClick={() => setInput(prompt)}
                              className="inline-flex min-h-9 items-center rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted hover:border-border"
                          >
                            {prompt}
                          </button>
                      ))}
                    </div>
                )}
              </div>
          ) : (
              <div className="space-y-5">
                {messages.map((msg) => {
                  const runtime = msg.clientRequestId ? requestRuntimesRef.current.get(msg.clientRequestId) : undefined;
                  const requestRunning = msg.requestStatus === 'queued' || msg.requestStatus === 'running';
                  return (
                    <div key={msg.id} data-client-request-id={msg.clientRequestId}>
                      <ChatMessage
                        message={msg}
                        chatWidth={chatMessagesWidth}
                        selectedFeedback={feedbackByMessageId[msg.id]}
                        onCitationClick={openSource}
                        onSourceOpen={openSource}
                        onRelatedQuestionClick={setInput}
                        onCopy={copyResponse}
                        onAction={handleResponseAction}
                        loadingAction={actionByMessage[msg.id]}
                        onFeedback={handleFeedback}
                        includeSourceExcerpts={includeSourceExcerpts}
                        showRetrievalDetails={showRetrievalDetails}
                      />
                      {requestRunning && msg.clientRequestId ? (
                        <RetrievalTimeline
                          events={msg.requestEvents ?? []}
                          elapsedSeconds={runtime ? Math.floor((performance.now() - runtime.startedAt) / 1000) : 0}
                          requestId={msg.clientRequestId}
                          onStop={() => stopGenerating(msg.clientRequestId!)}
                        />
                      ) : null}
                      {msg.requestError ? (
                        <div className="ml-auto mt-2 flex max-w-[46rem] items-center justify-between gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" data-testid="assistant-error" role="alert">
                          <span>{msg.requestError}</span>
                          {msg.retryPayload && msg.requestStatus !== 'cancelled' ? (
                            <button type="button" className="inline-flex shrink-0 items-center gap-1 rounded px-2 py-1 font-semibold hover:bg-destructive/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500" onClick={() => void handleSend(msg.retryPayload!.query, msg.retryPayload!.activeProfile, msg.retryPayload)} aria-label={`Retry request ${msg.clientRequestId ?? msg.id}`}>
                              <RefreshCw size={14}/>Retry
                            </button>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}

          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {backgroundIndexing > 0 && chatReady ? (
        <div className="mx-4 mb-1 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning-foreground" role="status">
          Updating the knowledge index in the background ({backgroundIndexing} queued or processing). You can keep chatting with the current index.
        </div>
      ) : null}

      <div className="assistant-composer-dock pointer-events-none absolute inset-x-0 bottom-0 z-20 px-2 pb-2 pt-8 sm:px-4 sm:pb-3">
        <AIComposerFrame>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={supportedFileTypes}
            className="hidden"
            onChange={(event) => handleFileChange(event.target.files)}
            data-testid="input-file-upload"
          />
          <div className="col-start-1 row-start-1 min-w-0 px-5 pb-1 pt-4 sm:px-7">
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
              placeholder="Ask a grounded question"
              className="block max-h-40 min-h-9 w-full resize-none overflow-y-auto bg-transparent py-1 text-[15px] leading-6 text-foreground outline-none placeholder:text-muted-foreground sm:text-base"
              data-testid="input-chat"
            />
          </div>

          <div className="col-start-1 row-start-2 flex min-w-0 items-center gap-1 px-3 pb-3 sm:px-5">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-accent hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              aria-label="Attach files"
              title="Attach files"
              data-testid="button-attach-file"
            >
              <Paperclip size={18} />
            </button>
            <div className="scrollbar-soft min-w-0 flex-1 overflow-x-auto pb-0.5" data-testid="composer-control-scroll">
              <ChatControlBar
                searchScope={searchScope}
                activeProfile={activeProfile}
                selectedContextCount={selectedContextItems.length}
                uploadedFileCount={uploadedFiles.length}
                onSearchScopeChange={(value) => updateActiveSession({ searchScope: value })}
                onActiveProfileChange={(value) => updateActiveSession({ activeProfile: value })}
                onManageContext={() => contextLocked ? toast({ title: 'Notebook sources are managed in Sources', description: 'Activate or deactivate attached sources from the notebook Sources panel.' }) : setContextManagerOpen(true)}
                onClearContext={clearActiveContext}
                includeSourceExcerpts={includeSourceExcerpts}
                showRetrievalDetails={showRetrievalDetails}
                onIncludeSourceExcerptsChange={setIncludeSourceExcerpts}
                onShowRetrievalDetailsChange={setShowRetrievalDetails}
                onResetQuerySettings={() => {
                  updateActiveSession({ searchScope: DEFAULT_SEARCH_SCOPE, activeProfile: DEFAULT_RESPONSE_LENGTH });
                  setIncludeSourceExcerpts(true);
                  setShowRetrievalDetails(true);
                }}
                attachedContext={(
                  <ContextChips
                    selectedContextItems={selectedContextItems}
                    uploadedFiles={effectiveUploadedFiles}
                    searchScope={searchScope}
                    onRemoveContext={(id) => activeSession.contextScope==='all_accessible' ? updateActiveSession({ selectedContextItems: selectedContextItems.filter((context) => context.id !== id) }) : toast({title:'Context is pinned',description:'Start a new conversation to use different context.'})}
                    onRemoveFile={(id) => updateActiveSession({ uploadedFiles: uploadedFiles.filter((file) => file.id !== id) })}
                    onManageContext={() => contextLocked ? toast({ title: 'Notebook sources are managed in Sources' }) : setContextManagerOpen(true)}
                  />
                )}
              />
            </div>
          </div>

          <button
            type="button"
            onClick={() => void handleSend()}
            disabled={!input.trim() || blockingAttachments.length > 0}
            className="composer-send col-start-2 row-span-2 row-start-1 mb-3 mr-3 inline-flex h-11 w-11 self-end items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm transition hover:bg-primary/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:bg-muted disabled:text-muted-foreground disabled:shadow-none sm:h-12 sm:w-12"
            data-testid="button-send"
            aria-label={chatReady ? 'Send message' : healthLabel}
            title={chatReady ? 'Send message' : healthLabel}
          >
            <Send size={18} />
          </button>
        </AIComposerFrame>

        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-1 pb-1 pt-2 text-[11px] leading-4 text-muted-foreground/90">
          <span>CIAL Knowledge OS uses AI to assist with enterprise knowledge. Responses may contain mistakes.</span>
          <span className="hidden shrink-0 sm:inline">Verify critical information against cited sources.</span>
        </div>
      </div>

      {!contextLocked ? <ContextManagerDialog
        open={contextManagerOpen}
        selectedItems={selectedContextItems}
        onApply={(items) => updateActiveSession({ selectedContextItems: items })}
        onClose={() => setContextManagerOpen(false)}
      /> : null}
      <SaveToKnowledgeDialog message={saveKnowledgeMessage} suggestedTitle={saveKnowledgeMessage?messages.slice(0,messages.findIndex((item)=>item.id===saveKnowledgeMessage.id)).reverse().find((item)=>item.role==='user')?.content:null} onClose={()=>setSaveKnowledgeMessage(null)}/>
    </div>
  );

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 overflow-hidden bg-background" data-testid="assistant-workspace">
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
          <ResizableHandle className="w-px bg-border after:hidden animate-in fade-in duration-200" />
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
      <ExportPreviewDialog open={exportDialogOpen} exportId={activeExportId} onOpenChange={setExportDialogOpen} onRegenerate={(format) => void regenerateExport(format)} />
    </div>
  );
}
