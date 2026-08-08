import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (relativePath) => readFileSync(path.join(frontendRoot, relativePath), 'utf8');

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(absolute);
    return /\.(?:ts|tsx)$/.test(entry.name) ? [absolute] : [];
  });
}

test('all frontend UUID generation is centralized and never falls back to Math.random', () => {
  const helperPath = path.join(frontendRoot, 'src/lib/browserCompatibility.ts');
  const helper = read('src/lib/browserCompatibility.ts');
  const unsafeConsumers = sourceFiles(path.join(frontendRoot, 'src')).filter((file) => {
    if (file === helperPath) return false;
    return /crypto\.randomUUID|navigator\.clipboard/.test(readFileSync(file, 'utf8'));
  });

  assert.deepEqual(unsafeConsumers.map((file) => path.relative(frontendRoot, file)), []);
  assert.match(helper, /typeof cryptoApi\?\.randomUUID === 'function'/);
  assert.match(helper, /cryptoApi\.getRandomValues\(new Uint8Array\(16\)\)/);
  assert.match(helper, /bytes\[6\].*0x40/);
  assert.match(helper, /bytes\[8\].*0x80/);
  assert.doesNotMatch(helper, /Math\.random/);
});

test('HTTP LAN browser fallbacks are explicit and the application has a top-level recovery boundary', () => {
  const helper = read('src/lib/browserCompatibility.ts');
  const main = read('src/main.tsx');
  const boundary = read('src/components/common/AppErrorBoundary.tsx');
  const packageJson = JSON.parse(read('package.json'));

  assert.match(helper, /document\.execCommand\('copy'\)/);
  assert.match(main, /<AppErrorBoundary>/);
  assert.match(main, /<App \/>/);
  assert.match(boundary, /getDerivedStateFromError/);
  assert.match(boundary, /componentDidCatch/);
  assert.match(boundary, /Reload application/);
  assert.equal(packageJson.scripts['verify:http-lan'], 'node scripts/verify_http_lan_compatibility.mjs');
  assert.ok(statSync(path.join(frontendRoot, 'scripts/verify_http_lan_compatibility.mjs')).isFile());
});
