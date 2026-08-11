import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

test('Vite configuration exposes no protected server secret names', () => {
  const files = [
    read('.env.example'),
    read('vite.config.ts'),
    read('src/api/client.ts'),
  ].join('\n');
  const protectedNames = [
    'CIAL_QDRANT_API_KEY',
    'CIAL_AUTH_SECRET_KEY',
    'DATABASE_URL',
    'CIAL_MIGRATION_DATABASE_URL',
  ];

  for (const name of protectedNames) {
    assert.doesNotMatch(files, new RegExp(name));
  }
  assert.doesNotMatch(files, /VITE_[A-Z0-9_]*(?:SECRET|PASSWORD|API_KEY)/);
});
