import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { listChatSessions } from '@/api/client';
import type { ChatHistorySession, SelectedContextItem } from '@/api/types';
import { toUiChatCitations, toUiChatSources } from '@/api/adapters';
import { useAuth } from '@/auth/AuthContext';
import type { AssistantChatMessage, AssistantSession, FeedbackType, ResponseLength, SearchScope, UploadedFileContext } from '@/types/assistant';
import { DEFAULT_RESPONSE_LENGTH, DEFAULT_SEARCH_SCOPE } from '@/data/assistantData';

const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY = 'cial-new-conversation-pending';
const NEW_CONVERSATION_EVENT = 'cial-new-conversation';

interface SessionUpdate { title?: string; messages?: AssistantChatMessage[]; selectedContextItems?: SelectedContextItem[]; uploadedFiles?: UploadedFileContext[]; searchScope?: SearchScope; activeProfile?: ResponseLength; feedbackByMessageId?: Record<string, FeedbackType[]>; }
interface AssistantSessionsValue {
  activeSession: AssistantSession;
  sessions: AssistantSession[];
  historyLoading: boolean;
  historyError: string | null;
  retryHistory: () => void;
  setActiveSession: (sessionId: string) => void;
  createNewSession: () => void;
  updateSession: (sessionId: string, update: SessionUpdate) => void;
  updateActiveSession: (update: SessionUpdate) => void;
  appendMessage: (sessionId: string, message: AssistantChatMessage) => void;
}

const AssistantSessionsContext = createContext<AssistantSessionsValue | null>(null);

function buildSession(value: Partial<AssistantSession> = {}): AssistantSession {
  const now = new Date().toISOString();
  return { id: value.id ?? crypto.randomUUID(), title: value.title ?? 'New conversation', messages: value.messages ?? [], selectedContextItems: value.selectedContextItems ?? [], uploadedFiles: value.uploadedFiles ?? [], searchScope: value.searchScope ?? DEFAULT_SEARCH_SCOPE, activeProfile: value.activeProfile ?? DEFAULT_RESPONSE_LENGTH, feedbackByMessageId: value.feedbackByMessageId ?? {}, createdAt: value.createdAt ?? now, updatedAt: value.updatedAt ?? now };
}

function fromApi(session: ChatHistorySession): AssistantSession {
  const feedbackByMessageId = Object.fromEntries(session.messages.filter((message) => message.feedback?.length).map((message) => [message.id, message.feedback as FeedbackType[]]));
  return buildSession({ id: session.id, title: session.title, createdAt: session.created_at, updatedAt: session.updated_at, feedbackByMessageId, messages: session.messages.map((message) => {
    const timestamp = new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (message.role === 'user') return { id: message.id, role: 'user', content: message.content, timestamp };
    const metadata = message.metadata;
    const response = { answer: message.content, citations: message.citations as never[], sources: message.sources as never[], metadata: metadata as never };
    return {
      id: message.id, role: 'assistant' as const, content: message.content, timestamp,
      citations: toUiChatCitations(response), sources: toUiChatSources(response),
      metadata: {
        searchScope: 'hybrid' as const,
        activeProfile: (typeof metadata.profile === 'string' ? metadata.profile : 'detailed') as ResponseLength,
        documentsSearched: Number(metadata.effective_document_count ?? new Set([...message.sources, ...message.citations].map((x) => x.document_id ?? x.relative_path ?? x.document_name).filter(Boolean)).size),
        chunksRetrieved: Number(metadata.selected_evidence_count ?? metadata.context_sections ?? message.sources.length),
        sourcesUsed: message.sources.length,
        citationCount: message.citations.length,
        confidence: message.citations.length > 0 ? 84 : 0,
        generationTimeSeconds: Number(metadata.latency_ms ?? 0) / 1000,
        transformationLabel: typeof metadata.label === 'string' ? metadata.label : undefined,
      },
    };
  }) });
}

function titleFrom(messages: AssistantChatMessage[]) { return messages.find((item) => item.role === 'user' && item.content.trim())?.content.trim().slice(0, 72) ?? 'New conversation'; }

export function AssistantSessionsProvider({ children }: { children: ReactNode }) {
  const { status, user } = useAuth();
  const [sessions, setSessions] = useState<AssistantSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const requestGeneration = useRef(0);
  const previousUser = useRef<string | null>(null);

  useEffect(() => {
    if (status !== 'authenticated' || !user) return;
    const userChanged = previousUser.current !== null && previousUser.current !== user.id;
    previousUser.current = user.id;
    if (userChanged) { setSessions([]); setActiveSessionId(null); }
    const generation = ++requestGeneration.current;
    const controller = new AbortController();
    setHistoryLoading(true); setHistoryError(null);
    void listChatSessions(controller.signal).then(({ sessions: records }) => {
      if (generation !== requestGeneration.current || controller.signal.aborted) return;
      const hydrated = records.map(fromApi);
      setSessions(hydrated);
      const requestedSession = new URLSearchParams(window.location.search).get('session');
      setActiveSessionId((current) => requestedSession && hydrated.some((item) => item.id === requestedSession) ? requestedSession : hydrated.some((item) => item.id === current) ? current : hydrated[0]?.id ?? null);
    }).catch((error: unknown) => {
      if (generation !== requestGeneration.current || controller.signal.aborted) return;
      setHistoryError(error instanceof Error ? error.message : 'Conversation history could not be loaded.');
    }).finally(() => { if (generation === requestGeneration.current) setHistoryLoading(false); });
    return () => controller.abort();
  }, [reload, status, user?.id]);

  const createNewSession = useCallback(() => {
    requestGeneration.current += 1;
    setHistoryLoading(false);
    let context: SelectedContextItem[] = [];
    try { context = JSON.parse(localStorage.getItem(ASSISTANT_CONTEXT_STORAGE_KEY) ?? '[]') as SelectedContextItem[]; } catch { context = []; }
    const draft = buildSession({ selectedContextItems: context });
    setSessions((current) => [draft, ...current]); setActiveSessionId(draft.id);
  }, []);

  useEffect(() => {
    const handler = () => { localStorage.removeItem(ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY); createNewSession(); };
    window.addEventListener(NEW_CONVERSATION_EVENT, handler);
    if (localStorage.getItem(ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY)) handler();
    return () => window.removeEventListener(NEW_CONVERSATION_EVENT, handler);
  }, [createNewSession]);

  const fallbackDraft = useMemo(() => buildSession(), []);
  const activeSession = sessions.find((item) => item.id === activeSessionId) ?? sessions[0] ?? fallbackDraft;
  const updateSession = useCallback((sessionId: string, update: SessionUpdate) => {
    requestGeneration.current += 1;
    setHistoryLoading(false);
    setSessions((current) => {
      const existing = current.find((session) => session.id === sessionId) ?? buildSession({ id: sessionId });
      const next = { ...existing, ...update, messages: update.messages ?? existing.messages, title: update.title ?? titleFrom(update.messages ?? existing.messages), updatedAt: new Date().toISOString() };
      return current.some((session) => session.id === sessionId) ? current.map((session) => session.id === sessionId ? next : session) : [next, ...current];
    });
  }, []);
  const updateActiveSession = useCallback((update: SessionUpdate) => updateSession(activeSession.id, update), [activeSession.id, updateSession]);
  const appendMessage = useCallback((sessionId: string, message: AssistantChatMessage) => {
    setSessions((current) => current.map((session) => session.id === sessionId
      ? { ...session, messages: [...session.messages, message], updatedAt: new Date().toISOString() }
      : session));
  }, []);
  const value = useMemo(() => ({ activeSession, sessions, historyLoading, historyError, retryHistory: () => setReload((value) => value + 1), setActiveSession: setActiveSessionId, createNewSession, updateSession, updateActiveSession, appendMessage }), [activeSession, sessions, historyLoading, historyError, createNewSession, updateSession, updateActiveSession, appendMessage]);
  return <AssistantSessionsContext.Provider value={value}>{children}</AssistantSessionsContext.Provider>;
}

export function useAssistantSessions() { const value = useContext(AssistantSessionsContext); if (!value) throw new Error('useAssistantSessions must be used within AssistantSessionsProvider.'); return value; }
