import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const context = read('src/components/assistant/AssistantSessionContext.tsx');
const panel = read('src/components/assistant/ChatPanel.tsx');
const history = read('src/components/assistant/ConversationHistory.tsx');

test('refresh, remount, and backend restart hydrate PostgreSQL history', () => {
  assert.match(context, /listChatSessions\(controller\.signal\)/);
  assert.doesNotMatch(context, /cial-assistant-sessions|INITIAL_ASSISTANT_MESSAGES/);
});

test('empty database and API failure do not install demo data', () => {
  assert.match(context, /useState<AssistantSession\[]>\(\[\]\)/);
  assert.match(history, /No conversations yet/);
  assert.doesNotMatch(`${context}\n${panel}`, /Runway edge light not working|MOCK_CHAT_SOURCES/);
  const failurePath = context.split('.catch((error: unknown) =>')[1].split('.finally')[0];
  assert.doesNotMatch(failurePath, /setSessions/);
});

test('slow responses and account changes cannot overwrite newer state', () => {
  assert.match(context, /generation !== requestGeneration\.current/);
  assert.match(context, /previousUser\.current !== user\.id/);
  assert.match(panel, /updateSession\(requestSessionId/);
});
