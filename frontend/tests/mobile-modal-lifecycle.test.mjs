import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const shell = read('src/components/layout/AppShell.tsx');
const mobile = read('src/components/layout/MobileSidebarDrawer.tsx');
const palette = read('src/components/common/CommandPalette.tsx');
const sheet = read('src/components/ui/sheet.tsx');
const workspace = read('src/pages/DocumentWorkspacePage.tsx');

test('global mobile navigation delegates scroll lock and focus lifecycle to controlled Radix Sheet', () => {
  assert.match(mobile, /<Sheet open=\{open\} onOpenChange=/);
  assert.match(mobile, /<SheetContent/);
  assert.match(mobile, /<SheetTitle className="sr-only">Global application navigation/);
  assert.match(mobile, /showCloseButton=\{false\}/);
  assert.doesNotMatch(mobile, /document\.body|body\.style|addEventListener\('keydown'/);
  assert.doesNotMatch(mobile, /lg:hidden/);
  assert.match(sheet, /showCloseButton\?: boolean/);
});

test('route and responsive transitions close the mobile navigation source of truth', () => {
  assert.match(shell, /MOBILE_NAVIGATION_QUERY = '\(max-width: 1023px\)'/);
  assert.match(shell, /setMobileOpen\(false\);\s*\}, \[location\]\)/);
  assert.match(shell, /if \(!event\.matches\) setMobileOpen\(false\)/);
  assert.match(shell, /open=\{mobileViewport && mobileOpen\}/);
  assert.match(mobile, /onClick=\{\(event\) => \{\s*onClose\(\)/);
  assert.match(mobile, /onClose\(\);\s*void logout\(\)/);
});

test('modal handoff closes navigation before search and keyboard shortcut cannot stack modals', () => {
  assert.match(mobile, /searchHandoffPending = React\.useRef\(false\)/);
  assert.match(mobile, /onCloseAutoFocus=\{\(event\) =>/);
  assert.match(mobile, /searchHandoffPending\.current = false;\s*window\.requestAnimationFrame\(\(\) => setOpen\(true\)\)/);
  assert.match(mobile, /searchHandoffPending\.current = true;\s*onClose\(\)/);
  assert.match(palette, /document\.querySelector\('\[role="dialog"\], \[aria-modal="true"\]'\)/);
  assert.match(palette, /if\(!value&&document\.querySelector/);
});

test('document workspace responsive panels close incompatible mobile dialog state', () => {
  assert.match(workspace, /CORPUS_TREE_PERSISTENT_QUERY = '\(min-width: 1280px\)'/);
  assert.match(workspace, /DOCUMENT_ASSISTANT_PERSISTENT_QUERY = '\(min-width: 1024px\)'/);
  assert.match(workspace, /setLeftOpen\(matches &&/);
  assert.match(workspace, /setRightOpen\(matches &&/);
  assert.match(workspace, /removeEventListener\('change',handleCorpusTreeChange\)/);
  assert.match(workspace, /removeEventListener\('change',handleDocumentAssistantChange\)/);
  assert.match(workspace, /pl-14 pr-3 shadow-xs backdrop-blur lg:px-3/);
  assert.doesNotMatch(workspace, /pl-14 pr-3[^\"]*sm:px-3/);
});
