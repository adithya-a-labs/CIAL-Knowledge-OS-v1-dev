import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const message = readFileSync(new URL('../src/components/assistant/ChatMessage.tsx', import.meta.url), 'utf8');
const panel = readFileSync(new URL('../src/components/assistant/ChatPanel.tsx', import.meta.url), 'utf8');
const adapter = readFileSync(new URL('../src/api/adapters.ts', import.meta.url), 'utf8');

test('copy uses the complete persisted Markdown answer and reports Copied', () => {
  assert.match(panel, /navigator\.clipboard\.writeText\(message\.content\)/);
  assert.match(message, /Copied/);
});

test('response actions use message-scoped APIs and stale generation guards', () => {
  assert.match(panel, /regenerateMessage\(message\.id\)/);
  assert.match(panel, /actionGenerationRef\.current\[message\.id\] !== generation/);
  assert.doesNotMatch(panel, /coming soon/);
});

test('explain simpler sends only the operation and message is appended atomically', () => {
  const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
  assert.match(client, /transformMessage\(messageId: string, operation:/);
  assert.match(client, /JSON\.stringify\(\{ operation \}\)/);
  assert.doesNotMatch(client.split('export function transformMessage', 2)[1].split('export function', 1)[0], /searchScope|selectedDocument|evidence|question/);
  assert.match(panel, /appendMessage\(actionSessionId, responseFromRecord\(record\)\)/);
  assert.match(panel, /actionGenerationRef\.current\[message\.id\] !== generation/);
});

test('explain simpler has message-scoped loading and accessible progress text', () => {
  assert.match(message, /Creating simpler explanation/);
  assert.match(message, /disabled=\{Boolean\(loadingAction\)\}/);
  assert.match(panel, /actionByMessage\[msg\.id\]/);
});

test('create checklist reuses the minimal transform request and accessible loading state', () => {
  const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
  const transformFunction = client.split('export function transformMessage', 2)[1].split('export function', 1)[0];
  assert.match(transformFunction, /JSON\.stringify\(\{ operation \}\)/);
  assert.doesNotMatch(transformFunction, /question|answer|searchScope|profile|selectedDocument|selectedFolder|chunk|citation|evidence/);
  assert.match(panel, /transformMessage\(message\.id, action\)/);
  assert.match(message, /Creating action checklist/);
  assert.match(message, /disabled=\{Boolean\(loadingAction\)\}/);
  assert.match(panel, /appendMessage\(actionSessionId, responseFromRecord\(record\)\)/);
});

test('metadata derives documents from source identity and separates citations', () => {
  assert.match(adapter, /new Set\(\[\.\.\.sources, \.\.\.citations\]/);
  assert.match(adapter, /citationCount: citations\.length/);
  assert.match(message, /evidence confidence/);
});
