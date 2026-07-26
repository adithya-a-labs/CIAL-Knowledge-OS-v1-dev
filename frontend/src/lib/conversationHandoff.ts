import type { ChatSessionCreatePayload, SelectedContextItem } from '@/api/types';
import type { ResponseLength } from '@/types/assistant';
import { startContextualConversation } from '@/lib/assistantNavigation';

export interface ConversationHandoff extends ChatSessionCreatePayload {
  question?: string;
  profile?: ResponseLength;
  contextItems?: SelectedContextItem[];
  autoSubmit?: boolean;
}

type Navigate = (to: string, options?: { replace?: boolean }) => void;

export function createConversationHandoff(
  navigate: Navigate,
  value: ConversationHandoff,
) {
  startContextualConversation(navigate, {
    title: value.title,
    origin: value.origin,
    contextScope: value.context_scope,
    contextItems: value.contextItems ?? [],
    question: value.question?.trim() || undefined,
    profile: value.profile,
    autoSubmit: value.autoSubmit ?? false,
  });
}
