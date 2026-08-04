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
const picker = readFileSync(new URL('../src/components/notebooks/NotebookSourcePicker.tsx', import.meta.url), 'utf8');
const corpusExplorer = readFileSync(new URL('../src/components/corpus/CorpusExplorer.tsx', import.meta.url), 'utf8');
const knowledgeCenter = readFileSync(new URL('../src/components/knowledge-center/KnowledgeCenter.tsx', import.meta.url), 'utf8');

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
  assert.match(page, /NotebookSourcePicker/);
  assert.match(picker, />My Workspace</);
  assert.match(picker, />Knowledge Center</);
  assert.match(picker, />Upload</);
  assert.match(picker, />Notes</);
  assert.match(picker, /uploadMyWorkspaceFiles/);
  assert.match(picker, /DocumentViewerPanel/);
  assert.match(picker, /Checkbox/);
});

test('notebook Knowledge Center reuses the shared hierarchical CorpusExplorer and removes the flat corpus list', () => {
  assert.match(knowledgeCenter, /<CorpusExplorer/);
  assert.match(picker, /<CorpusExplorer mode="select" embedded/);
  assert.match(corpusExplorer, /queryKey: \['corpus-tree'\]/);
  assert.match(corpusExplorer, /queryKey: \['corpus-folder', activePath\]/);
  assert.match(corpusExplorer, /<CorpusTree/);
  assert.match(corpusExplorer, /Corpus breadcrumbs/);
  assert.match(corpusExplorer, /Sort Corpus items/);
  assert.match(corpusExplorer, /Grid view/);
  assert.match(corpusExplorer, /List view/);
  assert.doesNotMatch(picker, /flattenCorpusTree|filteredCorpus|corpusDocuments/);
});

test('folder selections resolve authorized descendants and exclude duplicates and unavailable documents', () => {
  assert.match(corpusExplorer, /collectDocuments\(node\)/);
  assert.match(corpusExplorer, /document\.indexing_status === 'indexed' && !attachedDocumentIds\.has\(document\.id\)/);
  assert.match(corpusExplorer, /alreadyAttachedCount/);
  assert.match(corpusExplorer, /unavailableCount/);
  assert.match(corpusExplorer, /'indeterminate'/);
  assert.match(picker, /corpusSummary\.newDocuments/);
  assert.match(picker, /resolved documents/);
  assert.match(picker, /already attached/);
  assert.match(picker, /unavailable/);
  assert.match(picker, /disabled=\{attachmentPayload\.length === 0/);
});

test('embedded corpus preview preserves dialog selection and responsive layout contracts', () => {
  assert.match(picker, /onOpenDocument=\{openCorpusPreview\}/);
  assert.match(picker, /previewTrigger\.current/);
  assert.match(picker, /closePreview/);
  assert.match(picker, /sm:h-\[88vh\]/);
  assert.match(picker, /sm:w-\[90vw\]/);
  assert.match(picker, /safe-area-inset-bottom/);
  assert.match(corpusExplorer, /lg:hidden/);
  assert.match(corpusExplorer, /compact=\{embedded\}/);
  assert.match(corpusExplorer, /overflow-hidden/);
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
