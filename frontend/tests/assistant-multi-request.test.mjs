import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const panel = read('src/components/assistant/ChatPanel.tsx');
const sessions = read('src/components/assistant/AssistantSessionContext.tsx');
const types = read('src/types/assistant.ts');
const adapters = read('src/api/adapters.ts');
const client = read('src/api/client.ts');
const timeline = read('src/components/assistant/RetrievalTimeline.tsx');

test('request manager keeps controllers, token buffers, stages, and errors by request id', () => {
  assert.match(panel, /Map<string, LiveRequestRuntime>/);
  assert.match(panel, /requestRuntimesRef\.current\.set\(requestId, runtime\)/);
  assert.match(panel, /runtime\.controller/);
  assert.match(panel, /runtime\.tokenBuffer/);
  assert.match(panel, /runtime\.events/);
  assert.match(panel, /runtime\.degraded/);
  assert.match(types, /clientRequestId\?: string/);
  assert.match(types, /requestEvents\?:/);
});

test('two sends create ordered independent user and assistant placeholders', () => {
  const userAppend = panel.indexOf('appendMessage(requestSessionId, userMsg)');
  const assistantAppend = panel.indexOf('appendMessage(requestSessionId, placeholder)');
  const stream = panel.indexOf('const response = await streamQuestion');
  assert.ok(userAppend >= 0 && assistantAppend > userAppend && stream > assistantAppend);
  assert.match(panel, /id: `assistant-\$\{requestId\}`/);
  assert.match(panel, /requestStatus: 'queued'/);
  assert.match(panel, /updateMessage\(requestSessionId, placeholder\.id, aiMsg\)/);
  assert.doesNotMatch(panel, /if \(!question \|\| isLoading/);
});

test('composer stays enabled and Stop targets only its request', () => {
  assert.match(panel, /disabled=\{!input\.trim\(\) \|\| blockingAttachments\.length > 0\}/);
  assert.match(panel, /stopGenerating = \(requestId: string\)/);
  assert.match(panel, /requestRuntimesRef\.current\.get\(requestId\)\?\.controller/);
  assert.match(timeline, /aria-label=\{`Stop request \$\{requestId\}`\}/);
});

test('completion replaces placeholders without completion-time append ordering', () => {
  assert.match(panel, /updateMessage\(requestSessionId, userMsg\.id, persistedUserMsg\)/);
  assert.match(panel, /updateMessage\(requestSessionId, placeholder\.id, aiMsg\)/);
  assert.doesNotMatch(panel, /const completedMessages = \[\.\.\.messages/);
  assert.match(sessions, /messages\.map\(\(message\) => message\.id === messageId \? update : message\)/);
});

test('retry captures the original profile and selected context', () => {
  assert.match(types, /retryPayload\?: ChatRequestPayload/);
  assert.match(panel, /retryPayload: requestPayload/);
  assert.match(panel, /capturedPayload \?\?/);
  assert.match(panel, /handleSend\(msg\.retryPayload!\.query, msg\.retryPayload!\.activeProfile, msg\.retryPayload\)/);
});

test('draft materialization is single identity while chat execution is multi-flight', () => {
  assert.match(types, /requestSessionId: string/);
  assert.match(sessions, /id\.startsWith\(ASSISTANT_DRAFT_ID_PREFIX\) \? createUuid\(\) : id/);
  assert.match(panel, /const backendSessionId = activeSession\.requestSessionId/);
  assert.match(adapters, /client_request_id: clientRequestId/);
  assert.match(sessions, /sessionAliasesRef/);
});

test('ordinary chat requests omit the protected diagnostics flag for both chat transports', () => {
  const adapterFunction = adapters
    .split('export function toChatRequest', 2)[1]
    .split('export function', 1)[0];
  assert.doesNotMatch(adapterFunction, /include_debug/);
  assert.match(client, /request<ChatResponse>\('\/api\/chat'/);
  assert.match(client, /apiUrl\('\/api\/chat\/stream'\)/);
  assert.match(client, /body: JSON\.stringify\(payload\)/);
});

test('capacity errors retain the composer and auth invalidation aborts every stream', () => {
  assert.match(client, /new ApiError\(message, response\.status, detail\)/);
  assert.match(panel, /error instanceof ApiError && error\.status === 429/);
  assert.match(panel, /setInput\(\(current\) => current\.trim\(\) \? current : question\)/);
  assert.match(panel, /requestRuntimesRef\.current\.forEach/);
  assert.match(panel, /AUTH_INVALIDATED_EVENT/);
});

test('request completion logging reports the actual terminal outcome', () => {
  assert.match(panel, /let requestOutcome: 'completed' \| 'cancelled' \| 'failed' = 'failed'/);
  assert.match(panel, /requestOutcome = 'completed'/);
  assert.match(panel, /requestOutcome = cancelled \? 'cancelled' : 'failed'/);
  assert.match(panel, /status: requestOutcome/);
});

test('terminal cancellation clears a pending token frame before setting Stopped', () => {
  const catchStart = panel.indexOf('} catch (error) {');
  const cancelFrame = panel.indexOf('cancelAnimationFrame(runtime.tokenFrame)', catchStart);
  const terminalUpdate = panel.indexOf('requestStatus: cancelled', catchStart);
  assert.ok(catchStart >= 0 && cancelFrame > catchStart && terminalUpdate > cancelFrame);
  assert.match(panel, /runtime\.streamedText \+= runtime\.tokenBuffer/);
  assert.match(panel, /runtime\.tokenBuffer = ''/);
});
