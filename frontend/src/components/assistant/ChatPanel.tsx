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
import { createAssistantExport, getCorpusTree, regenerateMessage, streamQuestion, toggleMessageFeedback, transformMessage, uploadChatAttachment } from '@/api/client';
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
import { PENDING_COMPOSER_SUBMIT_KEY } from '@/lib/conversationHandoff';
import SaveToKnowledgeDialog from './SaveToKnowledgeDialog';

const supportedFileTypes = '.pdf,.docx,.pptx,.xlsx,.csv,.txt,image/*';
const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_CONTEXT_INTENT_STORAGE_KEY = 'cial-assistant-context-intent';
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

export default function ChatPanel() {
  const {
    activeSession,
    updateActiveSession,
    updateSession,
    appendMessage,
  } = useAssistantSessions();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionByMessage, setActionByMessage] = useState<Record<string, string>>({});
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [saveKnowledgeMessage,setSaveKnowledgeMessage]=useState<ChatMessageData|null>(null);
  const [activeExportId, setActiveExportId] = useState<string | null>(null);
  const exportSourceRef = useRef<{ sessionId: string; messageId: string; title: string } | null>(null);
  const actionGenerationRef = useRef<Record<string, number>>({});
  const [generationEvents, setGenerationEvents] = useState<GenerationEvent[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const tokenBufferRef = useRef('');
  const tokenFrameRef = useRef<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
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
  const activeRequestControllerRef = useRef<AbortController | null>(null);
  const isSubmittingRef = useRef(false);
  const activeRequestIdRef = useRef<string | null>(null);
  const retryQuestionRef = useRef<string | null>(null);
  const chatMessagesRef = useRef<HTMLDivElement>(null);
  const [chatMessagesWidth, setChatMessagesWidth] = useState<number>(0);
  const messages = activeSession.messages as ChatMessageData[];
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
    retryQuestionRef.current = null;
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
  }, [messages, isLoading, generationEvents]);

  useEffect(() => {
    if (!isLoading) {
      setElapsedSeconds(0);
      return;
    }
    const startedAt = Date.now();
    const interval = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => window.clearInterval(interval);
  }, [isLoading]);

  const stopGenerating = () => {
    const controller = activeRequestControllerRef.current;
    if (!controller || controller.signal.aborted) return;
    console.debug('[chat-request]', { requestId: activeRequestIdRef.current, status: 'cancelled_by_user' });
    controller.abort();
  };

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

  const handleSend = async (questionOverride?: string, profileOverride?: typeof activeProfile) => {
    const question = (questionOverride ?? input).trim();
    if (!question || isLoading || isSubmittingRef.current) return;
    if (blockingAttachments.length > 0) {
      const preparing = blockingAttachments.filter((file) => file.uploadStatus === 'uploading' || ['pending', 'indexing', undefined].includes(file.indexingStatus));
      toast({ title: preparing.length ? 'Preparing attached files' : 'An attached file is not ready',
        description: blockingAttachments.map((file) => file.name).join(', ') });
      return;
    }
    isSubmittingRef.current = true;

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
    const requestPayload: ChatRequestPayload = {
      query: question,
      searchScope,
      activeProfile: profileOverride ?? activeProfile,
      selectedDocumentIds: [...explicitDocumentIds, ...uploadedDocumentIds],
      selectedFolderIds: explicitFolderIds,
      selectedNoteIds: explicitNoteIds,
      uploadedFileIds: uploadedDocumentIds,
    };

    const userMsg: ChatMessageData = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: requestPayload.query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setIsLoading(true);
    setGenerationEvents([]);
    setStreamingText(''); tokenBufferRef.current = '';
    setErrorMessage(null);
    const controller = new AbortController();
    const requestId = `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    activeRequestControllerRef.current = controller;
    activeRequestIdRef.current = requestId;
    const startedAt = performance.now();
    console.debug('[chat-request]', { requestId, status: 'started' });

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
      const response = await streamQuestion(toChatRequest(requestPayload, requestSessionId), (event) => {
        if (event.type === 'stage') setGenerationEvents((current) => [...current, event].slice(-30));
        if (event.type === 'token' && event.delta && activeRequestControllerRef.current === controller) {
          tokenBufferRef.current += event.delta;
          if (tokenFrameRef.current === null) tokenFrameRef.current = requestAnimationFrame(() => { setStreamingText((current) => current + tokenBufferRef.current); tokenBufferRef.current = ''; tokenFrameRef.current = null; });
        }
      }, controller.signal, () => {
        updateSession(requestSessionId, { messages: [...messages, userMsg] });
        if (!questionOverride) setInput('');
        setGenerationEvents([{
          request_id: requestId,
          type: 'stage',
          stage_id: 'connection',
          status: 'completed',
          elapsed_ms: Math.round(performance.now() - startedAt),
          metrics: {},
        }]);
      });
      if (tokenFrameRef.current !== null) cancelAnimationFrame(tokenFrameRef.current);
      tokenFrameRef.current = null; tokenBufferRef.current = ''; setStreamingText('');
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
      };

      updateSession(requestSessionId, {
        messages: [...messages, persistedUserMsg, aiMsg],
      });
      retryQuestionRef.current = null;
    } catch (error) {
      const cancelled = controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError');
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
      setErrorMessage(message);
      if (!cancelled) retryQuestionRef.current = question;
      toast({
        title: cancelled ? 'Generation stopped' : 'Assistant request failed',
        description: message,
      });
    } finally {
      console.debug('[chat-request]', {
        requestId,
        status: controller.signal.aborted ? 'cancelled_by_user' : 'completed',
        elapsedSeconds: Math.round((performance.now() - startedAt) / 1000),
      });
      if (activeRequestControllerRef.current === controller) {
        activeRequestControllerRef.current = null;
        activeRequestIdRef.current = null;
      }
      isSubmittingRef.current = false;
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!chatReady || isLoading) return;
    const raw=localStorage.getItem(PENDING_COMPOSER_SUBMIT_KEY);if(!raw)return;
    try{
      const pending=JSON.parse(raw) as {sessionId:string;question:string;profile?:typeof activeProfile};
      if(pending.sessionId!==activeSession.id||!pending.question.trim())return;
      localStorage.removeItem(PENDING_COMPOSER_SUBMIT_KEY);
      void handleSend(pending.question,pending.profile);
    }catch{localStorage.removeItem(PENDING_COMPOSER_SUBMIT_KEY);}
  },[activeSession.id,chatReady,isLoading]);

  const handleFileChange = async (files: FileList | null) => {
    if (!files?.length) return;

    const queuedFiles = Array.from(files).map(createUploadedFileContext);
    updateActiveSession({
      uploadedFiles: [...uploadedFiles, ...queuedFiles],
    });
    if (fileInputRef.current) fileInputRef.current.value = '';

    const results = await Promise.allSettled(Array.from(files).map((file) => uploadChatAttachment(file, activeSession.id)));
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
      input.trim().length === 0 && !isLoading ? suggestedPrompts.slice(0, 5) : [];
  const hasSelectedSource = Boolean(selectedSource);
  const showDesktopSourcePane = hasSelectedSource && sourceViewerOpen && isDesktopViewport;
  const sourceViewerSources = allVisibleSources.map((source) => ({
            ...source,
            documentId: toUuidDocumentId(source.documentId) ?? source.documentId,
          }));
  const chatWorkspace = (
      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden" data-testid="chat-panel">
        <div
            ref={chatMessagesRef}
            className="scrollbar-soft min-h-0 flex-1 overflow-y-auto bg-[#fbfcfa] px-3 py-4 sm:px-4 xl:px-5"
            data-testid="chat-messages"
        >
          {messages.length === 0 ? (
              <div className="mx-auto flex h-full min-h-[36vh] max-w-2xl flex-col items-center justify-center px-4 py-10 text-center">
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-[#25611f]/10 text-[#25611f]">
                  <Bot size={22} />
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
                        onCopy={copyResponse}
                        onAction={handleResponseAction}
                        loadingAction={actionByMessage[msg.id]}
                        onFeedback={handleFeedback}
                        includeSourceExcerpts={includeSourceExcerpts}
                        showRetrievalDetails={showRetrievalDetails}
                    />
                ))}

            {isLoading && (
              <RetrievalTimeline events={generationEvents} elapsedSeconds={elapsedSeconds} onStop={stopGenerating} />
            )}

            {streamingText && <ChatMessage key="streaming-response" message={{ id: 'streaming-response', role: 'assistant', content: streamingText, timestamp: 'Generating…' }} chatWidth={chatMessagesWidth} onCitationClick={openSource} onSourceOpen={openSource} onRelatedQuestionClick={setInput} onCopy={copyResponse} onAction={handleResponseAction} loadingAction={undefined} onFeedback={handleFeedback} includeSourceExcerpts={includeSourceExcerpts} showRetrievalDetails={showRetrievalDetails}/>}

            {errorMessage && (
              <div className="flex items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" data-testid="assistant-error" role="alert">
                <span>{errorMessage}</span>
                {retryQuestionRef.current ? <button type="button" className="inline-flex shrink-0 items-center gap-1 rounded px-2 py-1 font-semibold hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500" onClick={() => void handleSend(retryQuestionRef.current ?? undefined)}><RefreshCw size={14}/>Retry</button> : null}
              </div>
            )}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {backgroundIndexing > 0 && chatReady ? (
        <div className="mx-4 mb-1 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900" role="status">
          Updating the knowledge index in the background ({backgroundIndexing} queued or processing). You can keep chatting with the current index.
        </div>
      ) : null}

      <div className="shrink-0 bg-white px-2 pb-2 pt-1 sm:px-4 sm:pb-3">
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
              className="block max-h-40 min-h-9 w-full resize-none overflow-y-auto bg-transparent py-1 text-[15px] leading-6 text-foreground outline-none placeholder:text-slate-500 sm:text-base"
              data-testid="input-chat"
            />
          </div>

          <div className="col-start-1 row-start-2 flex min-w-0 items-center gap-1 px-3 pb-3 sm:px-5">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-600 transition hover:bg-[#f1f6ee] hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
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
                onManageContext={() => setContextManagerOpen(true)}
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
                    onManageContext={() => setContextManagerOpen(true)}
                  />
                )}
              />
            </div>
          </div>

          <button
            type="button"
            onClick={() => void handleSend()}
            disabled={!input.trim() || isLoading || blockingAttachments.length > 0}
            className="col-start-2 row-span-2 row-start-1 mb-3 mr-3 inline-flex h-11 w-11 self-end items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm transition hover:bg-[#285f22] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:bg-[#d9dfd7] disabled:text-slate-500 disabled:shadow-none sm:h-12 sm:w-12"
            data-testid="button-send"
            aria-label={chatReady ? 'Send message' : healthLabel}
            title={chatReady ? 'Send message' : healthLabel}
          >
            <Send size={18} />
          </button>
        </AIComposerFrame>

        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-1 pt-1.5 text-[11px] leading-4 text-slate-500">
          <span>CIAL Knowledge OS uses AI to assist with enterprise knowledge. Responses may contain mistakes.</span>
          <span className="hidden shrink-0 sm:inline">Verify critical information against cited sources.</span>
        </div>
      </div>

      <ContextManagerDialog
        open={contextManagerOpen}
        selectedItems={selectedContextItems}
        onApply={(items) => updateActiveSession({ selectedContextItems: items })}
        onClose={() => setContextManagerOpen(false)}
      />
      <SaveToKnowledgeDialog message={saveKnowledgeMessage} suggestedTitle={saveKnowledgeMessage?messages.slice(0,messages.findIndex((item)=>item.id===saveKnowledgeMessage.id)).reverse().find((item)=>item.role==='user')?.content:null} onClose={()=>setSaveKnowledgeMessage(null)}/>
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
      <ExportPreviewDialog open={exportDialogOpen} exportId={activeExportId} onOpenChange={setExportDialogOpen} onRegenerate={(format) => void regenerateExport(format)} />
    </div>
  );
}
