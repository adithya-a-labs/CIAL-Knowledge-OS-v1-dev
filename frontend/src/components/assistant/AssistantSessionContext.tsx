import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useLocation } from 'wouter';
import { listChatSessions } from '@/api/client';
import type { ChatHistorySession, SelectedContextItem } from '@/api/types';
import { toUiChatCitations, toUiChatSources } from '@/api/adapters';
import { useAuth } from '@/auth/AuthContext';
import type {
  AssistantChatMessage,
  AssistantSession,
  FeedbackType,
  ResponseLength,
  SearchScope,
  UploadedFileContext,
} from '@/types/assistant';
import { DEFAULT_RESPONSE_LENGTH, DEFAULT_SEARCH_SCOPE } from '@/data/assistantData';
import {
  ASSISTANT_DRAFT_ID_PREFIX,
  ASSISTANT_NEW_CONVERSATION_EVENT,
  assistantConversationPath,
  clearConversationNavigationState,
  consumeContextualConversation,
  startNewConversation,
} from '@/lib/assistantNavigation';
import { createUuid } from '@/lib/browserCompatibility';

interface SessionUpdate {
  title?: string;
  messages?: AssistantChatMessage[];
  selectedContextItems?: SelectedContextItem[];
  uploadedFiles?: UploadedFileContext[];
  searchScope?: SearchScope;
  activeProfile?: ResponseLength;
  feedbackByMessageId?: Record<string, FeedbackType[]>;
}

interface PendingComposer {
  question: string;
  profile?: ResponseLength;
  autoSubmit: boolean;
}

interface AssistantSessionsValue {
  activeSession: AssistantSession;
  sessions: AssistantSession[];
  historyLoading: boolean;
  historyError: string | null;
  pendingComposer: PendingComposer | null;
  consumePendingComposer: () => void;
  retryHistory: () => void;
  setActiveSession: (sessionId: string) => void;
  createNewSession: () => void;
  promoteDraftSession: (draftId: string, sessionId: string, update: SessionUpdate) => void;
  updateSession: (sessionId: string, update: SessionUpdate) => void;
  updateActiveSession: (update: SessionUpdate) => void;
  appendMessage: (sessionId: string, message: AssistantChatMessage) => void;
  updateMessage: (sessionId: string, messageId: string, update: AssistantChatMessage) => void;
  removeRequestMessages: (sessionId: string, requestId: string) => void;
}

const AssistantSessionsContext = createContext<AssistantSessionsValue | null>(null);

function buildSession(value: Partial<AssistantSession> = {}): AssistantSession {
  const now = new Date().toISOString();
  const id = value.id ?? `${ASSISTANT_DRAFT_ID_PREFIX}${createUuid()}`;
  return {
    id,
    requestSessionId: value.requestSessionId ?? (
      id.startsWith(ASSISTANT_DRAFT_ID_PREFIX) ? createUuid() : id
    ),
    title: value.title ?? 'New conversation',
    messages: value.messages ?? [],
    selectedContextItems: value.selectedContextItems ?? [],
    uploadedFiles: value.uploadedFiles ?? [],
    searchScope: value.searchScope ?? DEFAULT_SEARCH_SCOPE,
    activeProfile: value.activeProfile ?? DEFAULT_RESPONSE_LENGTH,
    feedbackByMessageId: value.feedbackByMessageId ?? {},
    createdAt: value.createdAt ?? now,
    updatedAt: value.updatedAt ?? now,
    origin: value.origin ?? 'assistant',
    contextScope: value.contextScope ?? 'all_accessible',
  };
}

function fromApi(session: ChatHistorySession): AssistantSession {
  const feedbackByMessageId = Object.fromEntries(
    session.messages
      .filter((message) => message.feedback?.length)
      .map((message) => [message.id, message.feedback as FeedbackType[]]),
  );
  return buildSession({
    id: session.id,
    requestSessionId: session.id,
    title: session.title,
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    origin: session.origin,
    contextScope: session.context_scope,
    selectedContextItems: session.context_snapshot,
    feedbackByMessageId,
    messages: session.messages.map((message) => {
      const timestamp = new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      if (message.role === 'user') return { id: message.id, role: 'user', content: message.content, timestamp };
      const metadata = message.metadata;
      const response = {
        answer: message.content,
        citations: message.citations as never[],
        sources: message.sources as never[],
        metadata: metadata as never,
      };
      return {
        id: message.id,
        role: 'assistant' as const,
        content: message.content,
        timestamp,
        citations: toUiChatCitations(response),
        sources: toUiChatSources(response),
        metadata: {
          searchScope: 'hybrid' as const,
          activeProfile: (typeof metadata.profile === 'string' ? metadata.profile : 'detailed') as ResponseLength,
          documentsSearched: Number(
            metadata.effective_document_count
              ?? new Set([...message.sources, ...message.citations]
                .map((item) => item.document_id ?? item.relative_path ?? item.document_name)
                .filter(Boolean)).size,
          ),
          chunksRetrieved: Number(metadata.selected_evidence_count ?? metadata.context_sections ?? message.sources.length),
          sourcesUsed: message.sources.length,
          citationCount: message.citations.length,
          confidence: message.citations.length > 0 ? 84 : 0,
          generationTimeSeconds: Number(metadata.latency_ms ?? 0) / 1000,
          transformationLabel: typeof metadata.label === 'string' ? metadata.label : undefined,
        },
      };
    }),
  });
}

function titleFrom(messages: AssistantChatMessage[]) {
  return messages.find((item) => item.role === 'user' && item.content.trim())?.content.trim().slice(0, 72)
    ?? 'New conversation';
}

export function AssistantSessionsProvider({
  children,
  boundSessionId,
  boundTitle,
  boundContextItems,
}: {
  children: ReactNode;
  boundSessionId?: string;
  boundTitle?: string;
  boundContextItems?: SelectedContextItem[];
}) {
  const { status, user } = useAuth();
  const [location, navigate] = useLocation();
  const [sessions, setSessions] = useState<AssistantSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [draftSession, setDraftSession] = useState<AssistantSession | null>(null);
  const [pendingComposer, setPendingComposer] = useState<PendingComposer | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const requestGeneration = useRef(0);
  const previousUser = useRef<string | null>(null);
  const activeDraftIdRef = useRef<string | null>(null);
  const sessionAliasesRef = useRef<Record<string, string>>({});

  useEffect(() => {
    const resetToFreshDraft = () => {
      const draft = buildSession();
      activeDraftIdRef.current = draft.id;
      setActiveSessionId(null);
      setDraftSession(draft);
      setPendingComposer(null);
      clearConversationNavigationState();
    };
    window.addEventListener(ASSISTANT_NEW_CONVERSATION_EVENT, resetToFreshDraft);
    return () => window.removeEventListener(ASSISTANT_NEW_CONVERSATION_EVENT, resetToFreshDraft);
  }, []);

  useEffect(() => {
    if (boundSessionId) {
      activeDraftIdRef.current = null;
      setDraftSession(null);
      setPendingComposer(null);
      setActiveSessionId(boundSessionId);
      return;
    }
    const pathname = window.location.pathname;
    const query = new URLSearchParams(window.location.search);
    const routeMatch = pathname.match(/^\/assistant\/conversations\/([^/]+)$/);
    const legacySessionId = pathname === '/assistant' ? query.get('session') : null;
    const conversationId = routeMatch?.[1] ? decodeURIComponent(routeMatch[1]) : legacySessionId;

    if (conversationId) {
      activeDraftIdRef.current = null;
      setDraftSession(null);
      setPendingComposer(null);
      setActiveSessionId(conversationId);
      clearConversationNavigationState();
      if (legacySessionId) navigate(assistantConversationPath(conversationId), { replace: true });
      return;
    }

    const handoff = consumeContextualConversation(query.get('handoff'));
    const draft = buildSession({
      title: handoff?.title,
      origin: handoff?.origin,
      contextScope: handoff?.contextScope,
      selectedContextItems: handoff?.contextItems ?? [],
    });
    activeDraftIdRef.current = draft.id;
    setActiveSessionId(null);
    setDraftSession(draft);
    setPendingComposer(handoff?.question
      ? { question: handoff.question, profile: handoff.profile, autoSubmit: Boolean(handoff.autoSubmit) }
      : null);
    clearConversationNavigationState();
  }, [boundSessionId, location, navigate]);

  useEffect(() => {
    if (!boundSessionId) return;
    setSessions((current) => current.map((session) => session.id === boundSessionId ? {
      ...session,
      title: boundTitle ?? session.title,
      selectedContextItems: boundContextItems ?? session.selectedContextItems,
      contextScope: 'selected_context',
    } : session));
  }, [boundContextItems, boundSessionId, boundTitle]);

  useEffect(() => {
    if (status !== 'authenticated' || !user) return;
    const userChanged = previousUser.current !== null && previousUser.current !== user.id;
    previousUser.current = user.id;
    if (userChanged) {
      activeDraftIdRef.current = null;
      setSessions([]);
      setActiveSessionId(null);
      setDraftSession(null);
      setPendingComposer(null);
    }
    const generation = ++requestGeneration.current;
    const controller = new AbortController();
    setHistoryLoading(true);
    setHistoryError(null);
    void listChatSessions(controller.signal).then(({ sessions: records }) => {
      if (generation !== requestGeneration.current || controller.signal.aborted) return;
      const hydrated = records.map((record) => {
        const session = fromApi(record);
        return record.id === boundSessionId ? {
          ...session,
          title: boundTitle ?? session.title,
          selectedContextItems: boundContextItems ?? session.selectedContextItems,
          contextScope: 'selected_context',
        } : session;
      });
      setSessions((current) => {
        const hydratedIds = new Set(hydrated.map((item) => item.id));
        return [...current.filter((item) => !hydratedIds.has(item.id)), ...hydrated];
      });
    }).catch((error: unknown) => {
      if (generation !== requestGeneration.current || controller.signal.aborted) return;
      setHistoryError(error instanceof Error ? error.message : 'Conversation history could not be loaded.');
    }).finally(() => {
      if (generation === requestGeneration.current) setHistoryLoading(false);
    });
    return () => controller.abort();
  }, [boundContextItems, boundSessionId, boundTitle, reload, status, user?.id]);

  const createNewSession = useCallback(() => {
    startNewConversation(navigate);
  }, [navigate]);

  const setActiveSession = useCallback((sessionId: string) => {
    activeDraftIdRef.current = null;
    setDraftSession(null);
    setPendingComposer(null);
    setActiveSessionId(sessionId);
    navigate(assistantConversationPath(sessionId));
  }, [navigate]);

  const fallbackDraft = useMemo(() => buildSession(boundSessionId ? {
    id: boundSessionId,
    requestSessionId: boundSessionId,
    title: boundTitle ?? 'Notebook conversation',
    selectedContextItems: boundContextItems ?? [],
    contextScope: 'selected_context',
  } : {}), [boundContextItems, boundSessionId, boundTitle]);
  const activeSession = draftSession
    ?? sessions.find((item) => item.id === activeSessionId)
    ?? fallbackDraft;

  const updateSession = useCallback((sessionId: string, update: SessionUpdate) => {
    const resolvedSessionId = sessionAliasesRef.current[sessionId] ?? sessionId;
    setDraftSession((current) => {
      if (!current || current.id !== resolvedSessionId) return current;
      const messages = update.messages ?? current.messages;
      return {
        ...current,
        ...update,
        messages,
        title: update.title ?? titleFrom(messages),
        updatedAt: new Date().toISOString(),
      };
    });
    setSessions((current) => {
      const existing = current.find((session) => session.id === resolvedSessionId);
      if (!existing) return current;
      const messages = update.messages ?? existing.messages;
      const next = {
        ...existing,
        ...update,
        messages,
        title: update.title ?? titleFrom(messages),
        updatedAt: new Date().toISOString(),
      };
      return current.map((session) => session.id === resolvedSessionId ? next : session);
    });
  }, []);

  const promoteDraftSession = useCallback((draftId: string, sessionId: string, update: SessionUpdate) => {
    sessionAliasesRef.current[draftId] = sessionId;
    if (activeDraftIdRef.current !== draftId) return;
    activeDraftIdRef.current = null;
    setDraftSession((current) => {
      if (!current || current.id !== draftId) return current;
      const messages = update.messages ?? current.messages;
      const persisted = {
        ...current,
        ...update,
        id: sessionId,
        requestSessionId: sessionId,
        messages,
        title: update.title ?? titleFrom(messages),
        updatedAt: new Date().toISOString(),
      };
      setSessions((items) => [persisted, ...items.filter((item) => item.id !== sessionId)]);
      return null;
    });
    setActiveSessionId(sessionId);
    setPendingComposer(null);
    navigate(assistantConversationPath(sessionId), { replace: true });
  }, [navigate]);

  const updateActiveSession = useCallback(
    (update: SessionUpdate) => updateSession(activeSession.id, update),
    [activeSession.id, updateSession],
  );

  const appendMessage = useCallback((sessionId: string, message: AssistantChatMessage) => {
    const resolvedSessionId = sessionAliasesRef.current[sessionId] ?? sessionId;
    setDraftSession((current) => current?.id === resolvedSessionId
      ? { ...current, messages: [...current.messages, message], updatedAt: new Date().toISOString() }
      : current);
    setSessions((current) => current.map((session) => session.id === resolvedSessionId
      ? { ...session, messages: [...session.messages, message], updatedAt: new Date().toISOString() }
      : session));
  }, []);

  const updateMessage = useCallback((sessionId: string, messageId: string, update: AssistantChatMessage) => {
    const resolvedSessionId = sessionAliasesRef.current[sessionId] ?? sessionId;
    const replace = (session: AssistantSession) => session.id === resolvedSessionId
      ? {
          ...session,
          messages: session.messages.map((message) => message.id === messageId ? update : message),
          updatedAt: new Date().toISOString(),
        }
      : session;
    setDraftSession((current) => current ? replace(current) : current);
    setSessions((current) => current.map(replace));
  }, []);

  const removeRequestMessages = useCallback((sessionId: string, requestId: string) => {
    const resolvedSessionId = sessionAliasesRef.current[sessionId] ?? sessionId;
    const remove = (session: AssistantSession) => session.id === resolvedSessionId
      ? {
          ...session,
          messages: session.messages.filter((message) => message.clientRequestId !== requestId),
          updatedAt: new Date().toISOString(),
        }
      : session;
    setDraftSession((current) => current ? remove(current) : current);
    setSessions((current) => current.map(remove));
  }, []);

  const value = useMemo(() => ({
    activeSession,
    sessions,
    historyLoading,
    historyError,
    pendingComposer,
    consumePendingComposer: () => setPendingComposer(null),
    retryHistory: () => setReload((value) => value + 1),
    setActiveSession,
    createNewSession,
    promoteDraftSession,
    updateSession,
    updateActiveSession,
    appendMessage,
    updateMessage,
    removeRequestMessages,
  }), [
    activeSession,
    sessions,
    historyLoading,
    historyError,
    pendingComposer,
    setActiveSession,
    createNewSession,
    promoteDraftSession,
    updateSession,
    updateActiveSession,
    appendMessage,
    updateMessage,
    removeRequestMessages,
  ]);

  return <AssistantSessionsContext.Provider value={value}>{children}</AssistantSessionsContext.Provider>;
}

export function useAssistantSessions() {
  const value = useContext(AssistantSessionsContext);
  if (!value) throw new Error('useAssistantSessions must be used within AssistantSessionsProvider.');
  return value;
}
