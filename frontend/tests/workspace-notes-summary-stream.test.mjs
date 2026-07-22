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
  const editor = read('src/components/workspace/RichNoteEditor.tsx');
  assert.match(editor, /StableBlockId/);
  assert.match(editor, /data-block-id/);
  assert.match(editor, /tiptapToMarkdown/);
  assert.match(editor, /BubbleMenu/);
  assert.match(notes, /content_format: 'editor_json'/);
  assert.match(notes, /Add to AI context/);
  assert.match(notes, /listNoteTags/);
  assert.match(notes, /renameNoteTag/);
  assert.match(notes, /deleteNoteTag/);
  assert.match(notes, /linkNoteDocument/);
  assert.match(notes, /unlinkNoteDocument/);
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
  assert.match(page, /Export PDF/);
  assert.match(page, /Export DOCX/);
  assert.match(page, /saveSummaryToSavedKnowledge/);
  assert.match(page, /askSummaryFollowUp/);
  assert.match(client, /save-to-saved-knowledge/);
  assert.match(client, /ask-follow-up/);
  for (const contract of ['getCorpusTree', 'uploadMyWorkspaceFiles', 'listMyNotes', 'listChatSessions', 'Pasted text', "source_type:'folder'"]) assert.match(page, new RegExp(contract));
  const saved = read('src/components/workspace/SavedKnowledgeWorkspace.tsx');
  assert.match(saved, /listSavedKnowledge/);
  assert.match(saved, /removeSavedKnowledge/);
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
