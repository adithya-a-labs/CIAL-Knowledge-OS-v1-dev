import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const app = read('src/App.tsx');
const navigation = read('src/lib/assistantNavigation.ts');
const handoff = read('src/lib/conversationHandoff.ts');
const sessions = read('src/components/assistant/AssistantSessionContext.tsx');
const panel = read('src/components/assistant/ChatPanel.tsx');
const history = read('src/components/assistant/ConversationHistory.tsx');
const sidebar = read('src/components/layout/Sidebar.tsx');
const documentWorkspace = read('src/pages/DocumentWorkspacePage.tsx');

test('fresh, contextual draft, and existing-conversation routes have distinct contracts', () => {
  assert.match(app, /path="\/assistant\/new"/);
  assert.match(app, /path="\/assistant\/conversations\/:conversationId"/);
  assert.match(navigation, /ASSISTANT_FRESH_PATH = '\/assistant\/new'/);
  assert.match(navigation, /assistantConversationPath/);
  assert.match(navigation, /sessionStorage\.setItem/);
  assert.doesNotMatch(handoff, /createChatSession/);
});

test('sidebar AI Assistant and New Conversation share the canonical clean reset', () => {
  assert.match(sidebar, /item\.label !== 'AI Assistant'/);
  assert.match(sidebar, /startNewConversation\(navigate\)/);
  assert.match(navigation, /clearConversationNavigationState\(\)/);
  assert.match(navigation, /dispatchEvent\(new Event\(ASSISTANT_NEW_CONVERSATION_EVENT\)\)/);
  assert.match(navigation, /navigate\(ASSISTANT_FRESH_PATH\)/);
  assert.doesNotMatch(navigation, /\?reset=/);
  assert.match(sessions, /addEventListener\(ASSISTANT_NEW_CONVERSATION_EVENT/);
  for (const key of [
    'cial-assistant-selected-context',
    'cial-assistant-context-intent',
    'cial-new-conversation-pending',
    'cial-pending-composer-submit-v1',
  ]) {
    assert.match(navigation, new RegExp(key));
  }
});

test('fresh navigation cannot fall back to hydrated history or stale active state', () => {
  assert.doesNotMatch(sessions, /hydrated\[0\]\?\.id/);
  assert.doesNotMatch(sessions, /sessions\[0\] \?\?/);
  assert.match(sessions, /activeDraftIdRef\.current !== draftId/);
  assert.match(sessions, /generation !== requestGeneration\.current/);
  assert.match(panel, /requestRuntimesRef\.current/);
  assert.match(panel, /AUTH_INVALIDATED_EVENT/);
});

test('contextual handoff creates an isolated draft with only explicit context', () => {
  assert.match(handoff, /startContextualConversation\(navigate/);
  assert.match(handoff, /autoSubmit: value\.autoSubmit \?\? false/);
  assert.match(sessions, /selectedContextItems: handoff\?\.contextItems \?\? \[\]/);
  assert.match(documentWorkspace, /page_number:activePage/);
  assert.match(documentWorkspace, /chunk_id:requestedChunkId/);
  assert.match(panel, /selectedFolderIds: explicitFolderIds/);
  assert.match(panel, /pendingComposer\.autoSubmit/);
});

test('only explicit history selection opens a persisted conversation route', () => {
  assert.match(history, /setActiveSession\(session\.id\)/);
  assert.match(sessions, /navigate\(assistantConversationPath\(sessionId\)\)/);
  assert.match(sessions, /setActiveSessionId\(conversationId\)/);
});

test('fresh-chat requests share one materialization UUID then promote and replace the URL', () => {
  assert.match(sessions, /requestSessionId/);
  assert.match(sessions, /createUuid\(\)/);
  assert.match(panel, /const backendSessionId = activeSession\.requestSessionId/);
  assert.match(panel, /backendSessionId,\s*requestId/);
  assert.match(panel, /response\.session_id/);
  assert.match(panel, /promoteDraftSession\(requestSessionId, response\.session_id/);
  assert.match(sessions, /sessionAliasesRef\.current\[draftId\] = sessionId/);
  assert.match(sessions, /navigate\(assistantConversationPath\(sessionId\), \{ replace: true \}\)/);
});
