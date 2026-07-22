import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const card = read('src/components/knowledge-center/DocumentAnalysisCard.tsx');
const panel = read('src/components/knowledge-center/DocumentAssistantPanel.tsx');
const client = read('src/api/client.ts');
const workspace = read('src/pages/DocumentWorkspacePage.tsx');

test('document analysis uses typed API boundary and versioned React Query identity', () => {
  assert.match(client, /getDocumentAnalysis\(/);
  assert.match(client, /createDocumentAnalysis\(/);
  assert.match(client, /getDocumentAnalysisStatus|\/status/);
  assert.match(card, /document\.current_version_id\?\?document\.content_hash/);
  assert.match(card, /refetchInterval/);
  assert.match(card, /1500/);
});

test('analysis UI has real initial progress ready stale failure and duplicate-safe states', () => {
  assert.match(card, /Generate a grounded summary, key findings, and citations/);
  assert.match(card, /Preparing document analysis/);
  assert.match(card, /This analysis was generated for an earlier document version/);
  assert.match(card, /Analysis failed/);
  assert.match(card, /generate\.isPending\|\|active/);
  assert.match(card, /payload\.action_items/);
  assert.doesNotMatch(card, /dangerouslySetInnerHTML/);
});

test('analysis polling stops for every terminal state and retryable structured-output failures render Retry', () => {
  assert.match(card, /new Set\(\['completed','failed','cancelled','stale'\]\)/);
  assert.match(card, /!TERMINAL\.has\(status\)\?1500:false/);
  assert.match(card, /current\.retryable!==false/);
  assert.match(card, />Retry<\/button>/);
  assert.match(client, /retryable\?:boolean/);
});

test('citations use the existing page and chunk viewer synchronization without changing zoom', () => {
  assert.match(card, /onCitation\(citation\.page_number\?\?1,citation\.chunk_id\)/);
  assert.match(workspace, /setRequestedChunkId/);
  assert.match(workspace, /params\.set\('page'/);
  assert.doesNotMatch(card, /setZoom/);
});

test('follow-up remains document-scoped and mobile panel keeps sticky composer', () => {
  assert.match(card, /askSummaryFollowUp\(id,'original_versions'\)/);
  assert.match(panel, /sticky bottom-0/);
  assert.match(panel, /DocumentAnalysisCard/);
  assert.match(card, /role="dialog"/);
  assert.match(card, /motion-reduce:transition-none/);
});
