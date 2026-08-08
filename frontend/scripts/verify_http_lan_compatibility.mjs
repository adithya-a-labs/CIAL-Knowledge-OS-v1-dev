import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseURL = (process.env.CIAL_HTTP_LAN_TEST_URL || 'http://127.0.0.1:5173').replace(/\/$/, '');
const artifactDir = path.resolve('..', 'outputs', 'playwright', 'http-lan-compatibility');
const user = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'http-lan-verification@cial.in',
  display_name: 'HTTP LAN Verification',
  initials: 'HL',
  organization_name: 'CIAL',
  department_name: 'Validation',
  role_names: ['viewer'],
  permission_names: [],
  notifications_count: 0,
};
const runtimeErrors = [];
const failedRequests = [];

assert.ok(baseURL.startsWith('http://'), `Expected an HTTP origin, received ${baseURL}`);
await mkdir(artifactDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

await context.addInitScript((userId) => {
  Object.defineProperty(Crypto.prototype, 'randomUUID', {
    value: undefined,
    configurable: true,
  });
  localStorage.setItem(`cial-ai-notice-ack:${userId}`, '1');
  sessionStorage.setItem('cial-auth-session-entry', userId);
}, user.id);

await context.route((url) => url.pathname.startsWith('/api/'), async (route) => {
  const pathname = new URL(route.request().url()).pathname;
  if (pathname === '/api/auth/me') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user, message: 'Authenticated.' }) });
  }
  if (pathname === '/api/chat/sessions') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{"sessions":[]}' });
  }
  if (pathname === '/api/system/status') {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'green', label: 'System ready', chat_available: true, indexing_active: false,
        components: {}, index: { generation: 1, bm25_generation: 1, published_at: null, point_count: 1 },
        indexing: { worker_state: 'idle', worker_seen: true, worker_heartbeat_at: null, queue_depth: 0, queue_counts: {}, active_jobs: [], last_successful_index_at: null },
        models: { ollama: 'fixture', embedding: 'fixture', embedding_device: 'cpu', embedding_ready: true },
        gpu: { available: false, requested: false, device: 'cpu', utilization_percent: null, memory_used_mb: null, memory_total_mb: null },
        timestamps: { generated_at: new Date().toISOString(), worker_heartbeat_at: null, generation_published_at: null, last_successful_index_at: null },
        latency_ms: {}, lan_access: { enabled: true, mode: 'http', gateway_ready: true },
      }),
    });
  }
  if (pathname === '/api/chat/stream') {
    const answer = 'HTTP LAN compatibility verified.';
    const result = {
      request_id: 'http-lan-fixture', type: 'result', stage_id: 'complete', status: 'completed', elapsed_ms: 10,
      payload: {
        session_id: '00000000-0000-4000-8000-000000000100',
        user_message_id: '00000000-0000-4000-8000-000000000101',
        assistant_message_id: '00000000-0000-4000-8000-000000000102',
        answer, citations: [], sources: [],
        metadata: { retrieval_mode: 'hybrid', phase: 'verification', latency_ms: 10, model: 'fixture' },
      },
    };
    return route.fulfill({ status: 200, contentType: 'application/x-ndjson', body: `${JSON.stringify(result)}\n` });
  }
  if (pathname === '/api/workspaces/me/notes') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[],"total":0}' });
  }
  if (pathname === '/api/search/recent') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[]}' });
  }
  return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
});

const page = await context.newPage();
page.on('pageerror', (error) => runtimeErrors.push(error.message));
page.on('console', (message) => {
  if (message.type() === 'error') runtimeErrors.push(message.text());
});
page.on('requestfailed', (request) => {
  if (request.failure()?.errorText !== 'net::ERR_ABORTED') {
    failedRequests.push({ url: request.url(), reason: request.failure()?.errorText });
  }
});

let result;
try {
  await page.goto(`${baseURL}/assistant/new`, { waitUntil: 'networkidle' });
  assert.equal(await page.evaluate(() => typeof crypto.randomUUID), 'undefined');
  await page.getByTestId('input-chat').waitFor({ state: 'visible' });
  await page.getByTestId('input-chat').fill('Verify HTTP LAN initialization');
  await page.getByTestId('button-send').click();
  await page.getByText('HTTP LAN compatibility verified.').waitFor({ state: 'visible' });
  assert.equal(await page.getByText('CIAL couldn’t display this page').count(), 0);
  assert.deepEqual(runtimeErrors, []);
  assert.deepEqual(failedRequests, []);
  await page.screenshot({ path: path.join(artifactDir, 'assistant-http-lan.png'), fullPage: true });
  result = { generatedAt: new Date().toISOString(), baseURL, randomUUID: 'undefined', assistantInitialized: true, runtimeErrors, failedRequests, overall: 'pass' };
} catch (error) {
  result = {
    generatedAt: new Date().toISOString(), baseURL, randomUUID: await page.evaluate(() => typeof crypto.randomUUID).catch(() => 'unavailable'),
    assistantInitialized: false, runtimeErrors, failedRequests, url: page.url(), body: await page.locator('body').innerText().catch(() => ''),
    overall: 'fail', error: error instanceof Error ? error.message : String(error),
  };
  throw error;
} finally {
  await writeFile(path.join(artifactDir, 'verification-result.json'), `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  await context.close();
  await browser.close();
}

console.log(JSON.stringify({ overall: result.overall, baseURL, artifactDir }, null, 2));
