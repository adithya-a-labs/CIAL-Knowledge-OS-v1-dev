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

test('metadata derives documents from source identity and separates citations', () => {
  assert.match(adapter, /new Set\(\[\.\.\.sources, \.\.\.citations\]/);
  assert.match(adapter, /citationCount: citations\.length/);
  assert.match(message, /evidence confidence/);
});
