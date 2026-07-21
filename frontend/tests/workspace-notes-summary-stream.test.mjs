import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

test('notes UI uses durable APIs, revision autosave, and no production demo fallback', () => {
  const page = read('src/pages/WorkspacePage.tsx');
  const notes = read('src/components/workspace/NotesWorkspace.tsx');
  assert.match(page, /<NotesWorkspace/);
  assert.doesNotMatch(page, /fallbackFiles|demo-personal|Saved locally in this browser/);
  assert.match(notes, /750/);
  assert.match(notes, /expected_revision/);
  assert.match(notes, /Editing conflict/);
  assert.match(notes, /Move to Trash/);
});

test('summary entry and every visible result action map to real endpoints', () => {
  const home = read('src/data/homePageData.ts');
  const page = read('src/pages/SummaryWorkspacePage.tsx');
  const client = read('src/api/client.ts');
  assert.match(home, /\/workspace\/summaries\/new/);
  assert.match(page, /streamSummary/);
  assert.match(page, /saveSummaryToNote/);
  assert.match(page, /getSummaryExportUrl/);
  assert.match(client, /\/api\/summaries\/stream/);
});

test('generation status is inline, event-driven, accessible, and abortable', () => {
  const status = read('src/components/assistant/RetrievalTimeline.tsx');
  const panel = read('src/components/assistant/ChatPanel.tsx');
  assert.match(status, /role="status"/);
  assert.match(status, /aria-live="polite"/);
  assert.match(status, /aria-expanded/);
  assert.doesNotMatch(status, /ce-card|Preparing grounded answer|RETRIEVAL_STAGES/);
  assert.match(panel, /streamQuestion/);
  assert.match(panel, /controller\.abort/);
  assert.doesNotMatch(panel, /setInterval\(\(\) => \{\s*setActiveStageIndex/);
});
