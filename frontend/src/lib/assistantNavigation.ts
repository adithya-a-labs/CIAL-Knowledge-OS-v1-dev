import type { SelectedContextItem } from '@/api/types';
import type { ResponseLength } from '@/types/assistant';

export const ASSISTANT_FRESH_PATH = '/assistant/new';
export const ASSISTANT_DRAFT_ID_PREFIX = 'draft:';
export const ASSISTANT_NEW_CONVERSATION_EVENT = 'cial-assistant-new-conversation';

const HANDOFF_STORAGE_PREFIX = 'cial-assistant-handoff:';
const LEGACY_CONVERSATION_STORAGE_KEYS = [
  'cial-assistant-selected-context',
  'cial-assistant-context-intent',
  'cial-new-conversation-pending',
  'cial-pending-composer-submit-v1',
];

export interface AssistantContextualHandoff {
  title: string;
  origin: string;
  contextScope: string;
  contextItems: SelectedContextItem[];
  question?: string;
  profile?: ResponseLength;
  autoSubmit?: boolean;
}

type Navigate = (to: string, options?: { replace?: boolean }) => void;

export function isAssistantDraftId(sessionId: string) {
  return sessionId.startsWith(ASSISTANT_DRAFT_ID_PREFIX);
}

export function assistantConversationPath(conversationId: string) {
  return `/assistant/conversations/${encodeURIComponent(conversationId)}`;
}

export function clearConversationNavigationState() {
  LEGACY_CONVERSATION_STORAGE_KEYS.forEach((key) => window.localStorage.removeItem(key));
}

export function startNewConversation(navigate: Navigate) {
  clearConversationNavigationState();
  window.dispatchEvent(new Event(ASSISTANT_NEW_CONVERSATION_EVENT));
  navigate(ASSISTANT_FRESH_PATH);
}

export function startContextualConversation(
  navigate: Navigate,
  handoff: AssistantContextualHandoff,
) {
  clearConversationNavigationState();
  const token = crypto.randomUUID();
  window.sessionStorage.setItem(`${HANDOFF_STORAGE_PREFIX}${token}`, JSON.stringify(handoff));
  navigate(`${ASSISTANT_FRESH_PATH}?handoff=${encodeURIComponent(token)}`);
}

export function consumeContextualConversation(token: string | null) {
  if (!token) return null;
  const key = `${HANDOFF_STORAGE_PREFIX}${token}`;
  const raw = window.sessionStorage.getItem(key);
  window.sessionStorage.removeItem(key);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as AssistantContextualHandoff;
    return Array.isArray(parsed.contextItems) ? parsed : null;
  } catch {
    return null;
  }
}
