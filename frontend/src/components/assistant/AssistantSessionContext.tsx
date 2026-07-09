import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { INITIAL_ASSISTANT_MESSAGES } from '@/data/assistantData';
import type {
  AssistantChatMessage,
  AssistantSession,
  FeedbackType,
  ResponseLength,
  SearchScope,
  UploadedFileContext,
} from '@/types/assistant';
import type { SelectedContextItem } from '@/api/types';

const ASSISTANT_SESSIONS_STORAGE_KEY = 'cial-assistant-sessions';
const ASSISTANT_ACTIVE_SESSION_STORAGE_KEY = 'cial-assistant-active-session';
const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY = 'cial-new-conversation-pending';
const NEW_CONVERSATION_EVENT = 'cial-new-conversation';

interface SessionUpdate {
  title?: string;
  messages?: AssistantChatMessage[];
  selectedContextItems?: SelectedContextItem[];
  uploadedFiles?: UploadedFileContext[];
  searchScope?: SearchScope;
  activeProfile?: ResponseLength;
  feedbackByMessageId?: Record<string, FeedbackType>;
}

interface AssistantSessionsValue {
  activeSession: AssistantSession;
  sessions: AssistantSession[];
  setActiveSession: (sessionId: string) => void;
  createNewSession: () => void;
  clearHistory: () => void;
  updateActiveSession: (update: SessionUpdate) => void;
}

const AssistantSessionsContext = createContext<AssistantSessionsValue | null>(null);

function buildSession({
  id,
  title = 'New conversation',
  messages = [],
  selectedContextItems = [],
  uploadedFiles = [],
  searchScope = 'hybrid',
  activeProfile = 'detailed',
  feedbackByMessageId = {},
  createdAt,
  updatedAt,
}: Partial<AssistantSession> = {}): AssistantSession {
  const now = new Date().toISOString();
  return {
    id: id ?? `session-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    title,
    messages,
    selectedContextItems,
    uploadedFiles,
    searchScope,
    activeProfile,
    feedbackByMessageId,
    createdAt: createdAt ?? now,
    updatedAt: updatedAt ?? now,
  };
}

function initialSessions(): AssistantSession[] {
  const seededContext = (() => {
    try {
      const raw = window.localStorage.getItem(ASSISTANT_CONTEXT_STORAGE_KEY);
      return raw ? (JSON.parse(raw) as SelectedContextItem[]) : [];
    } catch {
      return [];
    }
  })();

  return [
    buildSession({
      title: 'Runway edge light not working',
      messages: INITIAL_ASSISTANT_MESSAGES as AssistantChatMessage[],
      selectedContextItems: seededContext,
    }),
  ];
}

function loadSessions(): AssistantSession[] {
  try {
    const raw = window.localStorage.getItem(ASSISTANT_SESSIONS_STORAGE_KEY);
    if (!raw) return initialSessions();
    const parsed = JSON.parse(raw) as Array<AssistantSession & { responseLength?: ResponseLength }>;
    if (!Array.isArray(parsed) || parsed.length === 0) return initialSessions();
    return parsed.map((session) =>
      buildSession({
        ...session,
        activeProfile: session.activeProfile ?? session.responseLength ?? 'detailed',
      }),
    );
  } catch {
    return initialSessions();
  }
}

function sessionTitleFromMessages(messages: AssistantChatMessage[]) {
  const firstUserMessage = messages.find((message) => message.role === 'user' && message.content.trim());
  if (!firstUserMessage) return 'New conversation';
  return firstUserMessage.content.trim().slice(0, 72);
}

export function AssistantSessionsProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<AssistantSession[]>(() => loadSessions());
  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    try {
      return (
        window.localStorage.getItem(ASSISTANT_ACTIVE_SESSION_STORAGE_KEY)
        ?? loadSessions()[0]?.id
        ?? buildSession().id
      );
    } catch {
      return loadSessions()[0]?.id ?? buildSession().id;
    }
  });

  const activeSession = useMemo(() => {
    return sessions.find((session) => session.id === activeSessionId) ?? sessions[0] ?? buildSession();
  }, [activeSessionId, sessions]);

  useEffect(() => {
    window.localStorage.setItem(ASSISTANT_SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    if (activeSession?.id) {
      window.localStorage.setItem(ASSISTANT_ACTIVE_SESSION_STORAGE_KEY, activeSession.id);
      window.localStorage.setItem(
        ASSISTANT_CONTEXT_STORAGE_KEY,
        JSON.stringify(activeSession.selectedContextItems),
      );
    }
  }, [activeSession]);

  useEffect(() => {
    const handleNewConversation = () => {
      window.localStorage.removeItem(ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY);
      const seededContext = (() => {
        try {
          const raw = window.localStorage.getItem(ASSISTANT_CONTEXT_STORAGE_KEY);
          return raw ? (JSON.parse(raw) as SelectedContextItem[]) : [];
        } catch {
          return [];
        }
      })();
      const newSession = buildSession({ selectedContextItems: seededContext });
      setSessions((current) => [...current, newSession]);
      setActiveSessionId(newSession.id);
    };

    window.addEventListener(NEW_CONVERSATION_EVENT, handleNewConversation);
    return () => window.removeEventListener(NEW_CONVERSATION_EVENT, handleNewConversation);
  }, []);

  useEffect(() => {
    const pending = window.localStorage.getItem(ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY);
    if (!pending) return;
    window.localStorage.removeItem(ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY);
    const newSession = buildSession();
    setSessions((current) => [...current, newSession]);
    setActiveSessionId(newSession.id);
  }, []);

  const updateActiveSession = (update: SessionUpdate) => {
    setSessions((current) =>
      current.map((session) => {
        if (session.id !== activeSession.id) return session;
        const nextMessages = update.messages ?? session.messages;
        return {
          ...session,
          ...update,
          messages: nextMessages,
          title: update.title ?? sessionTitleFromMessages(nextMessages),
          updatedAt: new Date().toISOString(),
        };
      }),
    );
  };

  const createNewSession = () => {
    const newSession = buildSession();
    setSessions((current) => [...current, newSession]);
    setActiveSessionId(newSession.id);
  };

  const clearHistory = () => {
    const fresh = buildSession();
    setSessions([fresh]);
    setActiveSessionId(fresh.id);
  };

  const value = useMemo<AssistantSessionsValue>(
    () => ({
      activeSession,
      sessions,
      setActiveSession: setActiveSessionId,
      createNewSession,
      clearHistory,
      updateActiveSession,
    }),
    [activeSession, sessions],
  );

  return (
    <AssistantSessionsContext.Provider value={value}>
      {children}
    </AssistantSessionsContext.Provider>
  );
}

export function useAssistantSessions() {
  const context = useContext(AssistantSessionsContext);
  if (!context) {
    throw new Error('useAssistantSessions must be used within AssistantSessionsProvider.');
  }
  return context;
}
