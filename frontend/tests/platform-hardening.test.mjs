import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

test('note autosave is serialized, revision-safe, conflict-aware, and delete-safe', () => {
  const queue = read('src/hooks/useSerializedNoteAutosave.ts');
  const workspace = read('src/components/workspace/NotesWorkspace.tsx');
  assert.match(queue, /inFlight\.current/);
  assert.match(queue, /revision\.current = saved\.revision/);
  assert.match(queue, /pending\.current = pending\.current \?\? draft/);
  assert.match(queue, /force,?/);
  assert.match(queue, /deleted\.current/);
  assert.match(workspace, /Review server version/);
  assert.match(workspace, /Keep mine/);
  assert.match(workspace, /Copy local draft/);
  assert.doesNotMatch(workspace, /server\.revision.*setTimeout/s);
});

test('health polling uses one shared adaptive React Query key and same-origin API', () => {
  const health = read('src/hooks/useBackendHealth.ts');
  const panel = read('src/components/assistant/ChatPanel.tsx');
  const client = read('src/api/client.ts');
  assert.match(health, /BACKEND_HEALTH_QUERY_KEY/);
  assert.match(health, /1_500/);
  assert.match(health, /20_000/);
  assert.match(health, /visibilityState/);
  assert.match(panel, /useBackendHealth\(\)/);
  assert.doesNotMatch(panel, /refetchInterval:\s*5000/);
  assert.match(client, /VITE_API_BASE_URL \?\? ''/);
});
