import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { extname } from 'node:path';
import test from 'node:test';

const frontendRoot = new URL('../', import.meta.url);
const read = (file) => readFileSync(new URL(file, frontendRoot), 'utf8');

function collectSourceFiles(relativeDirectory) {
  const directory = new URL(relativeDirectory, frontendRoot);
  const files = [];

  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const relativePath = `${relativeDirectory}${entry.name}`;
    if (entry.isDirectory()) files.push(...collectSourceFiles(`${relativePath}/`));
    else if (['.ts', '.tsx', '.css'].includes(extname(entry.name))) files.push(relativePath);
  }

  return files;
}

test('shared motion tokens and targeted reduced-motion policy remain source of truth', () => {
  const css = read('src/index.css');
  const expectedTokens = [
    '--motion-duration-press: 140ms',
    '--motion-duration-short: 160ms',
    '--motion-duration-standard: 180ms',
    '--motion-duration-panel: 220ms',
    '--motion-ease-enter: cubic-bezier(0.23, 1, 0.32, 1)',
    '--motion-ease-move: cubic-bezier(0.77, 0, 0.175, 1)',
    '--motion-ease-drawer: cubic-bezier(0.32, 0.72, 0, 1)',
  ];

  for (const token of expectedTokens) assert.ok(css.includes(token), `Missing ${token}`);
  assert.doesNotMatch(css, /0\.001ms/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]*scroll-behavior: auto/);
  assert.match(css, /\.animate-pulse,[\s\S]*animation: none !important/);
  assert.match(css, /\.appearance-toggle-thumb,[\s\S]*transition-duration: 0ms !important/);
});

test('appearance control synchronizes geometry, thumb, icon, and label state at 180ms', () => {
  const css = read('src/index.css');
  const appearanceRules = css.slice(css.indexOf('.appearance-toggle {'), css.indexOf('.app-shell {'));

  assert.doesNotMatch(appearanceRules, /\b(?:150|160|220)ms\b/);
  assert.match(appearanceRules, /transform var\(--motion-duration-standard\) var\(--motion-ease-move\)/);
  assert.match(appearanceRules, /color var\(--motion-duration-standard\) var\(--motion-ease-move\)/);
  assert.match(appearanceRules, /width var\(--motion-duration-standard\) var\(--motion-ease-move\)/);
  assert.match(appearanceRules, /height var\(--motion-duration-standard\) var\(--motion-ease-move\)/);
});

test('audited application scope never reintroduces broad transition-all utilities', () => {
  const files = [
    'src/index.css',
    ...collectSourceFiles('src/components/layout/'),
    ...collectSourceFiles('src/components/assistant/'),
    ...collectSourceFiles('src/components/knowledge-center/'),
    ...collectSourceFiles('src/components/documents/'),
    ...collectSourceFiles('src/components/workspace/'),
    ...collectSourceFiles('src/pages/'),
  ];
  const offenders = files.filter((file) => /\btransition-all\b|transition\s*:\s*all\b/.test(read(file)));

  assert.deepEqual(offenders, [], `Broad transitions found in: ${offenders.join(', ')}`);
});

test('graph hover and FAQ cards retain targeted, purposeful feedback', () => {
  const graph = read('src/pages/KnowledgeGraphPage.tsx');
  const faq = read('src/pages/FAQsPage.tsx');

  assert.match(graph, /className="motion-spatial origin-center transition-transform/);
  assert.match(graph, /\[transform-box:fill-box\]/);
  assert.doesNotMatch(graph, /r=\{isSelected \|\| isHovered/);
  assert.doesNotMatch(faq, /<article[^>]*hover:-translate/);
  assert.doesNotMatch(faq, /hover:-translate-y/);
});

test('JavaScript note navigation makes reduced-motion scrolling immediate', () => {
  const hook = read('src/hooks/useReducedMotionPreference.ts');
  const editor = read('src/components/workspace/RichNoteEditor.tsx');

  assert.match(hook, /prefers-reduced-motion: reduce/);
  assert.match(hook, /useSyncExternalStore/);
  assert.match(editor, /useReducedMotionPreference\(\)/);
  assert.match(editor, /behavior: prefersReducedMotion \? 'auto' : 'smooth'/);
});
