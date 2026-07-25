import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
const panel = readFileSync(new URL('../src/components/assistant/ChatPanel.tsx', import.meta.url), 'utf8');
const timeline = readFileSync(new URL('../src/components/assistant/RetrievalTimeline.tsx', import.meta.url), 'utf8');

test('chat stream has a bounded watchdog and preserves caller cancellation', () => {
  assert.match(client, /150_000/);
  assert.match(client, /TimeoutError/);
  assert.match(client, /removeEventListener\('abort'/);
});

test('assistant exposes retrieval and generation progress plus retry', () => {
  assert.match(timeline, /Retrieving sources/);
  assert.match(timeline, /Generating answer/);
  assert.match(timeline, /Completed/);
  assert.match(panel, /retryQuestionRef/);
  assert.match(panel, />Retry</);
  assert.match(panel, /onStop=\{stopGenerating\}/);
});

test('terminal failures clear the loading state', () => {
  assert.match(panel, /finally\s*\{/);
  assert.match(panel, /setIsLoading\(false\)/);
  assert.match(panel, /role="alert"/);
});
