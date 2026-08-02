import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
const page = readFileSync(new URL('../src/pages/NotebookWorkspacePage.tsx', import.meta.url), 'utf8');
const library = readFileSync(new URL('../src/pages/NotebooksPage.tsx', import.meta.url), 'utf8');
const sessions = readFileSync(new URL('../src/components/assistant/AssistantSessionContext.tsx', import.meta.url), 'utf8');
const chat = readFileSync(new URL('../src/components/assistant/ChatPanel.tsx', import.meta.url), 'utf8');
const shell = readFileSync(new URL('../src/components/layout/AppShell.tsx', import.meta.url), 'utf8');

test('notebook library and workspace routes are first-class protected routes', () => {
  assert.match(app, /path="\/notebooks" component=\{NotebooksPage\}/);
  assert.match(app, /path="\/notebooks\/:notebookId" component=\{NotebookWorkspacePage\}/);
  assert.match(shell, /isNotebookWorkspace/);
});

test('notebook server state uses stable React Query keys and real APIs', () => {
  for (const key of ['notebooks', 'notebookDetail', 'notebookSources', 'notebookArtifacts', 'notebookChatBinding']) {
    assert.match(`${page}\n${library}`, new RegExp(key));
  }
  for (const endpoint of ['/api/notebooks', '/sources', '/chat-session', '/artifacts']) {
    assert.match(client, new RegExp(endpoint.replaceAll('/', '\\/')));
  }
  assert.doesNotMatch(page, /demo|mock/i);
  assert.doesNotMatch(library, /demo|mock/i);
});

test('notebook chat composes the existing multi-request assistant and locks scope to Sources', () => {
  assert.match(page, /AssistantSessionsProvider/);
  assert.match(page, /<ChatPanel contextLocked/);
  assert.match(sessions, /boundSessionId/);
  assert.match(chat, /contextLocked/);
  assert.match(page, /active · .* attached/);
  assert.doesNotMatch(client, /notebooks\/.*chat\/stream/);
});

test('source picker unifies governed workspace, corpus, upload, and note flows', () => {
  assert.match(page, />My Workspace</);
  assert.match(page, />Knowledge Center</);
  assert.match(page, />Upload</);
  assert.match(page, />Notes</);
  assert.match(page, /uploadMyWorkspaceFiles/);
  assert.match(page, /getCorpusTree/);
  assert.match(page, /DocumentViewerPanel/);
  assert.match(page, /Checkbox/);
});

test('shared viewer, notes editor, supported outputs, and exports are reused', () => {
  assert.match(page, /SourceViewerPanel/);
  assert.match(page, /<NotesWorkspace/);
  for (const output of ['executive', 'detailed', 'key_points', 'action_items', 'comparison']) {
    assert.match(page, new RegExp(`type: '${output}'`));
  }
  for (const format of ['markdown', 'pdf', 'docx']) {
    assert.match(page, new RegExp(`'${format}'`));
  }
  assert.doesNotMatch(page, /audio|video|flashcard|mind map|infographic|slide deck/i);
});

test('responsive notebook uses named mobile tabs and one contextual panel owner', () => {
  for (const tab of ['Sources', 'Chat', 'Studio', 'Notes']) assert.match(page, new RegExp(`>${tab}<`));
  assert.match(page, /min-\[1440px\]/);
  assert.match(page, /tabletRightOpen/);
  assert.match(page, /cial-notebook-last-tab/);
});
