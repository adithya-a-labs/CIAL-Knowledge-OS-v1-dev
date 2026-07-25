import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const client = read('src/api/client.ts');
const hook = read('src/hooks/useSystemStatus.ts');
const indicator = read('src/components/assistant/AssistantSystemHealth.tsx');
const page = read('src/pages/AIAssistantPage.tsx');
const panel = read('src/components/assistant/ChatPanel.tsx');
const timeline = read('src/components/assistant/RetrievalTimeline.tsx');

test('assistant header polls and expands the authenticated live system status', () => {
  assert.match(client, /'\/api\/system\/status'/);
  assert.match(hook, /refetchInterval/);
  assert.match(hook, /status\.status === 'blue'/);
  assert.match(page, /<AssistantSystemHealth/);
  assert.match(indicator, /aria-expanded=\{expanded\}/);
  for (const detail of ['Generation', 'Queue', 'Worker', 'GPU', 'Model']) {
    assert.match(indicator, new RegExp(detail));
  }
  for (const label of ['System ready', 'Updating knowledge', 'Degraded', 'Unavailable']) {
    assert.match(`${indicator}\n${client}\n${read('src/api/types.ts')}`, new RegExp(label));
  }
});

test('submission performs a fresh preflight and blue status remains chat-capable', () => {
  assert.match(panel, /systemStatusQuery\.refetch\(\)/);
  assert.match(panel, /liveStatus\.data\.chat_available/);
  assert.doesNotMatch(panel, /if \(!chatReady\) \{/);
  assert.match(panel, /disabled=\{!input\.trim\(\) \|\| isLoading \|\| blockingAttachments\.length > 0\}/);
});

test('backend unavailable keeps the draft and exposes an actionable retry', () => {
  assert.match(panel, /if \(!liveStatus\.data\.chat_available\)/);
  assert.match(panel, /The assistant cannot start this request yet/);
  assert.match(panel, /retryQuestionRef\.current = question/);
  assert.match(panel, /role="alert"/);
  assert.doesNotMatch(
    panel.slice(panel.indexOf('const handleSend'), panel.indexOf('const explicitDocumentIds')),
    /setInput\(''\)/,
  );
});

test('successful Enter and button submission use the same reliable handler', () => {
  assert.match(panel, /event\.key === 'Enter' && !event\.shiftKey/);
  assert.match(panel, /onClick=\{\(\) => void handleSend\(\)\}/);
  assert.match(panel, /isSubmittingRef\.current/);
  assert.match(panel, /setIsLoading\(false\)/);
});

test('connection failure retains input while degraded indicator state remains dynamic', () => {
  assert.match(client, /SYSTEM_STATUS_TIMEOUT_MS/);
  assert.match(indicator, /query\.isError \? 'red'/);
  assert.match(indicator, /query\.isError \? 'Unavailable'/);
  assert.match(indicator, /status\?\.label/);
});

test('draft clearing and optimistic persistence occur only after stream initiation', () => {
  const streamCall = panel.indexOf('const response = await streamQuestion');
  const clear = panel.indexOf("if (!questionOverride) setInput('');", streamCall);
  const connectCallback = panel.indexOf('}, controller.signal, () => {', streamCall);
  assert.ok(streamCall >= 0);
  assert.ok(connectCallback > streamCall);
  assert.ok(clear > connectCallback);
  assert.match(client, /onConnected\?\.\(\)/);
  assert.match(panel, /retryQuestionRef\.current = question/);
});

test('progress labels reflect actual connection, retrieval, generation and terminal stages', () => {
  for (const label of [
    'Connected',
    'Validating request',
    'Loading published generation',
    'Searching',
    'Reranking',
    'Generating',
    'Completed',
    'Failed',
  ]) {
    assert.match(timeline, new RegExp(label));
  }
});
