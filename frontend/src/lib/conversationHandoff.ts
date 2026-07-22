import { createChatSession } from '@/api/client';
import type { ChatSessionCreatePayload, SelectedContextItem } from '@/api/types';

export const PENDING_COMPOSER_SUBMIT_KEY = 'cial-pending-composer-submit-v1';

export interface ConversationHandoff extends ChatSessionCreatePayload {
  question?: string;
  profile?: string;
  contextItems?: SelectedContextItem[];
}

export async function createConversationHandoff(value: ConversationHandoff) {
  const session = await createChatSession({
    title: value.title,
    origin: value.origin,
    created_from_document: value.created_from_document ?? null,
    context_scope: value.context_scope,
    selected_document_ids: value.selected_document_ids,
    selected_note_ids: value.selected_note_ids ?? [],
  });
  const contextItems = value.contextItems ?? session.context_snapshot;
  localStorage.setItem('cial-assistant-selected-context', JSON.stringify(contextItems));
  localStorage.setItem('cial-assistant-context-intent', String(Date.now()));
  if (value.question?.trim()) {
    localStorage.setItem(PENDING_COMPOSER_SUBMIT_KEY, JSON.stringify({ sessionId: session.id, question: value.question.trim(), profile: value.profile ?? 'standard' }));
  }
  return session;
}
