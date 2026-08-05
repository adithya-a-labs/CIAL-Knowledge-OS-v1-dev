import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const workspace = readFileSync(
  new URL('../src/pages/DocumentWorkspacePage.tsx', import.meta.url),
  'utf8',
);

test('compact document panels retain an interruptible exit lifecycle', () => {
  assert.match(workspace, /function useCompactPanelPresence\(open: boolean, persistent: boolean\)/);
  assert.match(workspace, /requestAnimationFrame\(\(\) => setVisible\(true\)\)/);
  assert.match(workspace, /clearTimeout\(timeout\)/);
  assert.match(workspace, /\(\(leftOpen&&corpusTreePersistent\)\|\|leftCompactPanel\.mounted\)/);
  assert.match(workspace, /\(\(rightOpen&&documentAssistantPersistent\)\|\|rightCompactPanel\.mounted\)/);
  assert.doesNotMatch(workspace, /leftOpen&&!corpusTreePersistent\?<div/);
  assert.doesNotMatch(workspace, /rightOpen&&!documentAssistantPersistent\?<div/);
});

test('compact document motion uses shared tokens and directional spatial continuity', () => {
  assert.match(workspace, /transition-\[transform,opacity\] duration-\[var\(--motion-duration-panel\)\]/);
  assert.match(workspace, /ease-\[var\(--motion-ease-drawer\)\]/);
  assert.match(workspace, /-translate-x-full opacity-0/);
  assert.match(workspace, /translate-x-full opacity-0/);
  assert.match(workspace, /motion-reduce:translate-x-0/);
  assert.match(workspace, /transition-opacity duration-\[var\(--motion-duration-panel\)\]/);
  assert.doesNotMatch(workspace, /transition-all|animate-in/);
});

test('closing panels leave the modal and focus lifecycle immediately', () => {
  assert.match(workspace, /role=\{!corpusTreePersistent&&leftCompactPanel\.visible\?'dialog':undefined\}/);
  assert.match(workspace, /aria-hidden=\{!corpusTreePersistent&&!leftCompactPanel\.visible\?true:undefined\}/);
  assert.match(workspace, /leftOpen&&!corpusTreePersistent&&leftCompactPanel\.visible/);
  assert.match(workspace, /rightOpen&&!documentAssistantPersistent&&rightCompactPanel\.visible/);
  assert.match(workspace, /previousFocus\?\.focus\(\)/);
  assert.match(workspace, /if\(event\.key==='Escape'\)/);
});
