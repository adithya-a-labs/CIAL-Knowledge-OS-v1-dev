import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (file) => readFileSync(new URL(`../${file}`, import.meta.url), 'utf8');
const main = read('src/main.tsx');
const provider = read('src/components/theme/ThemeProvider.tsx');
const control = read('src/components/theme/AppearanceControl.tsx');
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
  assert.match(sidebar, /<AppearanceControl collapsed=\{collapsed\}/);
  assert.match(mobile, /<AppearanceControl menuSide="top"/);
  assert.match(control, /Appearance: \$\{selectedOption\.label\}/);
  assert.match(control, /appearance-trigger-collapsed/);
  assert.match(control, /DropdownMenuRadioGroup/);
  assert.match(control, /appearance-option-\$\{option\.value\}/);
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
