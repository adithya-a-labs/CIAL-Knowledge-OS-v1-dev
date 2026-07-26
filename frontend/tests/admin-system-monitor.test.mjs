import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const app = read('src/App.tsx');
const page = read('src/pages/AdminSystemMonitorPage.tsx');
const denied = read('src/pages/AdminAccessDeniedPage.tsx');
const hook = read('src/hooks/useAdminSystemMonitor.ts');
const client = read('src/api/client.ts');
const sidebar = read('src/components/layout/Sidebar.tsx');

test('admin system monitor route is protected before generic admin routes', () => {
  const monitorRoute = app.indexOf('path="/admin/system-monitor"');
  const genericRoute = app.indexOf('path="/admin/:sub"');
  assert.ok(monitorRoute >= 0);
  assert.ok(genericRoute > monitorRoute);
  assert.match(page, /monitor_system/);
  assert.match(page, /manage_settings/);
  assert.match(page, /<AdminAccessDeniedPage \/>/);
  assert.match(denied, /403 · Restricted/);
  assert.match(denied, /Access denied/);
});

test('normal navigation exposes the console only for monitor permissions', () => {
  assert.match(sidebar, /canMonitorSystem/);
  assert.match(sidebar, /permission_names/);
  assert.match(sidebar, /\{canMonitorSystem \?/);
  assert.match(sidebar, /href="\/admin\/system-monitor"/);
});

test('dashboard renders every required live operations section', () => {
  for (const label of [
    'AI Operations Console',
    'Live indexing pipeline',
    'GPU monitoring',
    'Worker monitoring',
    'Query pipeline',
    'Queue management',
    'Live event stream',
  ]) {
    assert.match(page, new RegExp(label));
  }
  for (const component of ['Backend', 'Database', 'Qdrant', 'Indexer', 'GPU', 'Models']) {
    assert.match(page, new RegExp(`name="${component}"`));
  }
  assert.match(page, /Current stage/);
  assert.match(page, /Failed stage:/);
  assert.match(page, /timeout_reason/);
  assert.match(page, /generation_metrics/);
  assert.match(page, /tokens_per_second/);
  assert.match(page, /chat_priority_active/);
  assert.match(page, /ollama_processor_type/);
  assert.match(page, /gpu_layers_used/);
  assert.match(page, /generation_gpu_utilization/);
  assert.match(page, /cpu_offload_detected/);
  assert.match(page, /Configured device/);
  assert.match(page, /Actual model device/);
  assert.match(page, /Embedding model/);
  assert.match(page, /Batch latency/);
});

test('monitor uses authenticated SSE with reconnect and stale detection', () => {
  assert.match(client, /'\/api\/admin\/system\/monitor'/);
  assert.match(client, /'\/api\/admin\/system\/stream'/);
  assert.match(client, /Accept: 'text\/event-stream'/);
  assert.match(client, /credentials: 'include'/);
  assert.match(hook, /reconnecting/);
  assert.match(hook, /auth-failed/);
  assert.match(hook, /Date\.now\(\) - lastUpdateRef\.current > 7_000/);
  assert.match(hook, /Math\.min\(1000 \* 2 \*\* retryCount, 15_000\)/);
});

test('dashboard handles disconnected, stale, and partial unavailable states', () => {
  assert.match(page, /Stale telemetry/);
  assert.match(page, /Last known values remain visible/);
  assert.match(page, /Reconnect/);
  assert.match(page, /Unavailable/);
  assert.match(page, /componentStatus/);
});
