import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const panel = read('src/components/assistant/ChatPanel.tsx');
const controls = read('src/components/assistant/ChatControlBar.tsx');
const settings = read('src/components/assistant/AssistantSettingsPopover.tsx');
const context = read('src/components/assistant/ContextChips.tsx');
const more = read('src/components/assistant/ComposerMoreMenu.tsx');
const message = read('src/components/assistant/ChatMessage.tsx');
const sources = read('src/components/assistant/SourceCitationCard.tsx');
const session = read('src/components/assistant/AssistantSessionContext.tsx');

test('compact composer keeps the input primary and Context, Scope, Length, attachment, send, and More accessible', () => {
  assert.match(panel, /data-testid="compact-chat-composer"/);
  assert.match(panel, /grid-rows-\[minmax\(3rem,auto\)_auto\]/);
  assert.match(context, /\{totalContextCount\} item/);
  assert.match(context, /ShieldCheck/);
  assert.match(settings, /selectedOption\.title/);
  assert.match(controls, /attachedContext/);
  assert.match(controls, /<ComposerMoreMenu/);
  assert.match(panel, /data-testid="composer-control-scroll"/);
  assert.match(panel, /data-testid="button-attach-file"/);
  assert.match(panel, /data-testid="button-send"/);
  assert.doesNotMatch(panel, /backend-status-chip/);
});

test('More exposes supported controls and resets the existing defaults', () => {
  for (const label of ['Manage context', 'Clear attached context', 'Hard retrieval boundary', 'Include source excerpts', 'Show retrieval details', 'Reset query settings']) {
    assert.match(more, new RegExp(label));
  }
  assert.doesNotMatch(more, /debug metadata|max answer length|Advanced settings/i);
  assert.match(more, /disabled=\{!hasContext\}/);
  assert.match(more, /checked=\{hasContext\}/);
  assert.match(more, /onIncludeSourceExcerptsChange/);
  assert.match(more, /onShowRetrievalDetailsChange/);
  assert.match(controls, /DEFAULT_SEARCH_SCOPE/);
  assert.match(controls, /DEFAULT_RESPONSE_LENGTH/);
  assert.match(session, /searchScope: value\.searchScope \?\? DEFAULT_SEARCH_SCOPE/);
});

test('context selector contains filenames and supports manage and remove actions without permanent filename chips', () => {
  assert.match(context, /data-testid="context-selector-popover"/);
  assert.match(context, /selectedContextItems\.map/);
  assert.match(context, /uploadedFiles\.map/);
  assert.match(context, /onRemoveContext\(item\.id\)/);
  assert.match(context, /onRemoveFile\(file\.id\)/);
  assert.match(context, /onManageContext\(\)/);
  assert.match(context, /PopoverTrigger asChild/);
  assert.match(context, /aria-label=\{`Manage selected context:/);
});

test('context removal and clear update the same session arrays used by outgoing requests', () => {
  assert.match(panel, /selectedContextItems: \[\]/);
  assert.match(panel, /uploadedFiles: \[\]/);
  assert.match(panel, /selectedDocumentIds: \[\.\.\.explicitDocumentIds, \.\.\.uploadedDocumentIds\]/);
  assert.match(panel, /selectedFolderIds: explicitFolderIds/);
  assert.match(panel, /selectedNoteIds: explicitNoteIds/);
  assert.match(controls, /scopeLocked = totalContextCount > 0/);
  assert.match(controls, /disabled=\{scopeLocked\}/);
});

test('private notes are searchable context items and retain hard-boundary semantics', () => {
  const manager = read('src/components/assistant/ContextManagerDialog.tsx');
  assert.match(manager, /listMyNotes/);
  assert.match(manager, /type:'note'/);
  assert.match(manager, /Private/);
  assert.match(context, /NotebookPen/);
  assert.match(panel, /item\.type === 'note'/);
});

test('real token deltas are buffered per animation frame and stale requests are ignored', () => {
  assert.match(panel, /event\.type === 'token'/);
  assert.match(panel, /requestAnimationFrame/);
  assert.match(panel, /activeRequestControllerRef\.current === controller/);
  assert.match(panel, /streamingText/);
});

test('source summary is collapsed by default and replaces permanent citation/source cards', () => {
  assert.match(sources, /useState\(false\)/);
  assert.match(sources, /hidden=\{!expanded\}/);
  assert.match(sources, /aria-expanded=\{expanded\}/);
  assert.match(sources, /aria-controls=\{contentId\}/);
  assert.doesNotMatch(message, /assistant-citations|CitationList/);
  assert.match(message, /hasCitations \? <SourceCitationCard sources=\{sources\}/);
  assert.match(message, /includeExcerpts=\{includeSourceExcerpts\}/);
  assert.match(message, /showRetrievalDetails && message\.metadata/);
});

test('source grouping prefers stable document id and deduplicates pages and citation ids in order', () => {
  assert.match(sources, /source\.noteId \|\| source\.documentId/);
  assert.match(sources, /if \(stableId\) return `id:\$\{stableId\}`/);
  assert.match(sources, /source\.relativePath \|\| source\.documentTitle/);
  assert.match(sources, /const groups = new Map<string, GroupedSource>\(\)/);
  assert.match(sources, /!existing\.pages\.includes\(page\)/);
  assert.match(sources, /!existing\.citationIds\.includes\(source\.citationIndex\)/);
  assert.match(sources, /groups\.map\(\(group\)/);
  assert.match(sources, /onOpenSource\(group\.sources\[0\]\)/);
});

test('composer retains multiline growth, enter submission, loading disablement, and mobile containment', () => {
  assert.match(panel, /resizeComposerTextarea/);
  assert.match(panel, /event\.key === 'Enter' && !event\.shiftKey/);
  assert.match(panel, /max-h-40/);
  assert.match(panel, /disabled=\{!input\.trim\(\) \|\| isLoading \|\| !chatReady \|\| blockingAttachments\.length > 0\}/);
  assert.match(panel, /min-w-0/);
  assert.match(panel, /overflow-x-auto/);
  assert.match(panel, /min-h-\[108px\]/);
});
