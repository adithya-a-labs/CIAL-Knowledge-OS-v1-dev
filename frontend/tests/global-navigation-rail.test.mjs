import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const shell = read('src/components/layout/AppShell.tsx');
const sidebar = read('src/components/layout/Sidebar.tsx');
const workspace = read('src/pages/DocumentWorkspacePage.tsx');
const navigation = read('src/data/homePageData.ts');

test('document workspace retains one persistent global navigation rail', () => {
  assert.match(shell, /cial-global-nav-collapsed/);
  assert.match(shell, /!hasGlobalNavPreference\.current/);
  assert.match(shell, /hasGlobalNavPreference\.current = true/);
  assert.match(shell, /handleGlobalNavCollapsedChange/);
  assert.match(shell, /<Sidebar/);
  assert.doesNotMatch(shell, /!isDocumentWorkspace\?<Sidebar/);
  assert.match(shell, /globalNavCollapsed \? 'lg:pl-16' : 'lg:pl-60'/);
  assert.match(sidebar, /collapsed \? 'w-16' : 'w-60'/);
  assert.match(sidebar, /duration-200 ease-out/);
});

test('collapsed navigation is labelled, tooltip-enabled, and route-aware', () => {
  assert.match(sidebar, /RailTooltip/);
  assert.match(sidebar, /focus-visible:ring-2/);
  assert.match(sidebar, /aria-current=\{active \? 'page'/);
  assert.match(sidebar, /aria-label=\{item\.label\}/);
  assert.match(sidebar, /Expand global navigation/);
  assert.match(navigation, /Knowledge Center/);
  assert.match(sidebar, /New Conversation/);
});

test('corpus tree and assistant remain separate responsive workspace panels', () => {
  assert.match(workspace, /data-testid="corpus-tree-panel"/);
  assert.match(workspace, /CORPUS_TREE_PERSISTENT_QUERY = '\(min-width: 1280px\)'/);
  assert.match(workspace, /xl:relative/);
  assert.match(workspace, /data-testid="document-assistant-panel"/);
  assert.match(workspace, /DOCUMENT_ASSISTANT_PERSISTENT_QUERY = '\(min-width: 1024px\)'/);
  assert.match(workspace, /lg:relative/);
  assert.match(workspace, /setRightOpen\(false\)/);
  assert.match(workspace, /setLeftOpen\(false\)/);
  assert.doesNotMatch(workspace, /CIAL Knowledge OS/);
});
