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
    ...collectSourceFiles('src/components/dashboard/'),
    ...collectSourceFiles('src/components/ui/'),
    ...collectSourceFiles('src/pages/'),
  ];
  const offenders = files.filter((file) => /\btransition-all\b|transition\s*:\s*all\b/.test(read(file)));

  assert.deepEqual(offenders, [], `Broad transitions found in: ${offenders.join(', ')}`);
});

test('shared primitives use the motion vocabulary without delaying repeated work', () => {
  const sheet = read('src/components/ui/sheet.tsx');
  const tooltip = read('src/components/ui/tooltip.tsx');
  const progress = read('src/components/ui/progress.tsx');
  const tabs = read('src/components/ui/tabs.tsx');

  assert.match(sheet, /duration-\[var\(--motion-duration-panel\)\]/);
  assert.match(sheet, /ease-\[var\(--motion-ease-drawer\)\]/);
  assert.doesNotMatch(sheet, /duration-(?:300|500)|ease-in-out/);
  assert.match(tooltip, /data-\[state=delayed-open\]:animate-in/);
  assert.doesNotMatch(tooltip, /(?<!delayed-open\]:)animate-in/);
  assert.match(progress, /value=\{value\}/);
  assert.match(progress, /transition-transform/);
  assert.match(tabs, /transition-\[background-color,color,box-shadow\]/);
});

test('graph hover and FAQ cards retain targeted, purposeful feedback', () => {
  const css = read('src/index.css');
  const graph = read('src/pages/KnowledgeGraphPage.tsx');
  const faq = read('src/pages/FAQsPage.tsx');

  assert.match(graph, /className="knowledge-graph-node motion-spatial origin-center transition-transform/);
  assert.match(graph, /\[transform-box:fill-box\]/);
  assert.doesNotMatch(graph, /r=\{isSelected \|\| isHovered/);
  assert.doesNotMatch(graph, /onMouseEnter|onMouseLeave|hoveredNode/);
  assert.match(css, /@media \(hover: hover\) and \(pointer: fine\)[\s\S]*graph-node-[\s\S]*knowledge-graph-node/);
  assert.doesNotMatch(faq, /<article[^>]*hover:-translate/);
  assert.doesNotMatch(faq, /hover:-translate-y/);
});

test('non-interactive cards remain static and expose only real controls as interactive', () => {
  const css = read('src/index.css');
  const collections = read('src/components/workspace/CollectionCard.tsx');
  const staticCards = [
    read('src/components/common/StatCard.tsx'),
    read('src/components/workspace/WorkspaceStatCard.tsx'),
    read('src/pages/AnalyticsPage.tsx'),
    read('src/pages/ExpertDirectoryPage.tsx'),
    read('src/pages/LearningHubPage.tsx'),
    read('src/pages/KnowledgeGapsPage.tsx'),
    read('src/pages/AdminSettingsPage.tsx'),
  ].join('\n');

  assert.doesNotMatch(css, /\.fluid-card:hover/);
  assert.doesNotMatch(collections, /className="[^"]*cursor-pointer[^"]*"\s+data-testid=\{`collection-card/);
  assert.match(collections, /aria-label=\{`More actions for \$\{collection\.name\}`\}/);
  assert.doesNotMatch(staticCards, /fluid-card[^"\n]*hover:(?:border|shadow)/);
});

test('JavaScript note navigation makes reduced-motion scrolling immediate', () => {
  const hook = read('src/hooks/useReducedMotionPreference.ts');
  const editor = read('src/components/workspace/RichNoteEditor.tsx');

  assert.match(hook, /prefers-reduced-motion: reduce/);
  assert.match(hook, /useSyncExternalStore/);
  assert.match(editor, /useReducedMotionPreference\(\)/);
  assert.match(editor, /behavior: prefersReducedMotion \? 'auto' : 'smooth'/);
});
