import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (file) => readFileSync(new URL(`../${file}`, import.meta.url), 'utf8');
const main = read('src/main.tsx');
const provider = read('src/components/theme/ThemeProvider.tsx');
const control = read('src/components/theme/AppearanceToggle.tsx');
const sidebar = read('src/components/layout/Sidebar.tsx');
const mobile = read('src/components/layout/MobileSidebarDrawer.tsx');
const css = read('src/index.css');
const html = read('index.html');

test('theme provider owns class-based Light/System/Dark persistence', () => {
  assert.match(main, /<ThemeProvider>/);
  assert.match(provider, /attribute="class"/);
  assert.match(provider, /defaultTheme="system"/);
  assert.match(provider, /enableSystem/);
  assert.match(provider, /storageKey="cial-theme"/);
  assert.match(control, /value: 'light'/);
  assert.match(control, /value: 'system'/);
  assert.match(control, /value: 'dark'/);
});

test('appearance control is shared by expanded, collapsed, and mobile navigation', () => {
  assert.match(sidebar, /<AppearanceToggle variant=\{collapsed \? 'collapsed' : 'expanded'\}/);
  assert.match(mobile, /<AppearanceToggle variant="mobile"/);
  assert.match(control, /role="radiogroup"/);
  assert.match(control, /role="radio"/);
  assert.match(control, /aria-checked=\{selected\}/);
  assert.match(control, /tabIndex=\{selected \? 0 : -1\}/);
  assert.match(control, /appearance-option-\$\{option\.value\}/);
});

test('appearance toggle uses deterministic adaptive geometry and keyboard navigation', () => {
  assert.match(control, /orientation = variant === 'collapsed' \? 'vertical' : 'horizontal'/);
  assert.match(control, /event\.key === 'ArrowLeft'/);
  assert.match(control, /event\.key === 'ArrowRight'/);
  assert.match(control, /event\.key === 'ArrowUp'/);
  assert.match(control, /event\.key === 'ArrowDown'/);
  assert.match(control, /event\.key === 'Home'/);
  assert.match(control, /event\.key === 'End'/);
  assert.match(control, /restoreFocusIndexRef/);
  assert.match(control, /useLayoutEffect/);
  assert.match(css, /\.appearance-toggle-thumb/);
  assert.match(css, /grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(css, /grid-template-rows: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(css, /@container \(max-width: 270px\)/);
  assert.match(css, /prefers-reduced-motion: reduce/);
});

test('dark palette keeps an absolute-black canvas with botanical surface hierarchy', () => {
  assert.match(css, /\.dark\s*\{/);
  assert.match(css, /--background:\s*0 0% 0%/);
  assert.match(css, /--sidebar:\s*120 33% 1%/);
  assert.match(css, /--card:\s*120 17% 2%/);
  assert.match(css, /--popover:\s*108 24% 4%/);
  assert.match(css, /--foreground:\s*90 20% 96%/);
  assert.match(css, /--heading-foreground:\s*0 0% 100%/);
  assert.match(css, /--border:\s*109 18% 12%/);
  assert.match(css, /\.dark \.app-shell[\s\S]*radial-gradient/);
  assert.match(css, /\.dark \.assistant-composer/);
});

test('dark green intensity is expressed through semantic hierarchy tokens', () => {
  assert.match(css, /--dark-green-primary:\s*103 36% 49%/);
  assert.match(css, /--dark-green-active:\s*106 30% 54%/);
  assert.match(css, /--dark-green-muted:\s*106 27% 44%/);
  assert.match(css, /--dark-green-border:\s*109 36% 27%/);
  assert.match(css, /--dark-green-surface:\s*116 38% 8%/);
  assert.match(css, /--dark-green-surface-subtle:\s*113 36% 5%/);
  assert.match(css, /--dark-green-text-soft:\s*106 30% 70%/);
  assert.match(css, /--dark-user-message-start:\s*108 33% 30%/);
  assert.match(css, /--dark-user-message-end:\s*107 34% 35%/);
  assert.match(css, /--dark-citation-surface:\s*113 36% 9%/);
  assert.match(css, /--dark-citation-text:\s*105 35% 58%/);
  assert.match(css, /--dark-grounded-identity:\s*106 36% 45%/);
  assert.match(css, /\.dark \.user-message-bubble/);
  assert.match(css, /\.dark \.inline-citation/);
  assert.match(css, /\.dark \.grounded-response-icon/);
  assert.match(css, /\.dark \.sidebar-utility-action/);
  assert.match(css, /\.dark \.composer-send:not\(:disabled\)/);
});

test('startup bootstrap does not invent a preference', () => {
  assert.match(html, /localStorage\.getItem\('cial-theme'\)/);
  assert.doesNotMatch(html, /localStorage\.setItem\('cial-theme'/);
  assert.match(html, /prefers-color-scheme: dark/);
});

test('semantic document and status surfaces remain intentional in dark mode', () => {
  assert.match(css, /--code-block:/);
  assert.match(css, /--selection:/);
  assert.match(css, /--success:/);
  assert.match(css, /--warning:/);
  assert.match(css, /--info:/);
  assert.match(css, /\.document-paper/);
  assert.match(css, /\.document-search-hit/);
});
