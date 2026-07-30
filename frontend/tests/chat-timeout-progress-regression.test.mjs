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
  assert.match(timeline, /Loading published generation/);
  assert.match(timeline, /Searching knowledge/);
  assert.match(timeline, /Reranking sources/);
  assert.match(timeline, /Generating answer/);
  assert.match(timeline, /Completed/);
  assert.match(panel, /retryPayload/);
  assert.match(panel, /runtime\.degraded/);
  assert.match(panel, /Retrieval completed with degradation/);
  assert.match(panel, /<RefreshCw size=\{14\}\/>Retry/);
  assert.match(panel, /onStop=\{\(\) => stopGenerating\(msg\.clientRequestId!\)\}/);
});

test('stream errors expose the backend failed stage and retry reason', () => {
  assert.match(client, /failed_stage/);
  assert.match(client, /Failed stage:/);
  assert.match(client, /failure\.reason/);
});

test('terminal failures clear only the matching request runtime', () => {
  assert.match(panel, /finally\s*\{/);
  assert.match(panel, /requestRuntimesRef\.current\.delete\(requestId\)/);
  assert.match(panel, /requestStatus: cancelled \? 'cancelled' : 'failed'/);
  assert.match(panel, /role="alert"/);
});
