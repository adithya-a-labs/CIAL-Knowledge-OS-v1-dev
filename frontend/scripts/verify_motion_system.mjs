import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseURL = (process.env.CIAL_MOTION_TEST_URL || 'http://127.0.0.1:5173').replace(/\/$/, '');
const artifactDir = path.resolve('..', 'outputs', 'playwright', 'motion-system');
const sessionId = '00000000-0000-4000-8000-000000000101';
const user = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'motion@cial.in',
  display_name: 'Motion Verification',
  initials: 'MV',
  organization_name: 'CIAL',
  department_name: 'Validation',
  role_names: ['viewer'],
  permission_names: [],
  notifications_count: 0,
};

const metadata = { retrieval_mode: 'hybrid', phase: '4.5', latency_ms: 40, model: 'fixture' };
const longSources = Array.from({ length: 8 }, (_, index) => ({
  id: `S${index + 1}`,
  document_name: index < 4 ? 'Airport Operations Manual.pdf' : `Reference ${index + 1}.txt`,
  path: `/fixture/reference-${index + 1}.txt`,
  relative_path: `/fixture/reference-${index + 1}.txt`,
  document_id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
  page: index + 1,
  page_number: index + 1,
  chunk_id: `chunk-${index + 1}`,
  text: `Variable-length source excerpt ${index + 1}. `.repeat(index + 2),
  file_type: 'txt',
  mime_type: 'text/plain',
  file_url: `/api/corpus/document/fixture-${index + 1}/file`,
  score: 0.9 - index * 0.02,
  source_type: 'document',
}));
const historyMessages = Array.from({ length: 28 }, (_, index) => {
  const role = index % 2 === 0 ? 'user' : 'assistant';
  const last = index === 27;
  return {
    id: `history-${index}`,
    role,
    content: role === 'user'
      ? `Question ${index / 2 + 1}: explain the applicable operational procedure.`
      : `Grounded answer ${Math.ceil(index / 2)}. ${'Calm enterprise response content. '.repeat(10)}`,
    citations: last ? longSources.map((source) => ({
      id: source.id,
      document_name: source.document_name,
      document_id: source.document_id,
      relative_path: source.relative_path,
      page: source.page,
      page_number: source.page_number,
      chunk_id: source.chunk_id,
      snippet: source.text,
      file_type: source.file_type,
      mime_type: source.mime_type,
      file_url: source.file_url,
      score: source.score,
      source_type: source.source_type,
    })) : [],
    sources: last ? longSources : [],
    metadata,
    created_at: new Date(Date.now() - (28 - index) * 60_000).toISOString(),
    feedback: [],
  };
});
const session = {
  id: sessionId,
  title: 'Motion verification conversation',
  messages: historyMessages,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  origin: 'assistant',
  created_from_document: null,
  context_scope: 'all_accessible',
  selected_document_ids: [],
  selected_note_ids: [],
  context_snapshot: [],
};

const systemStatus = {
  status: 'green', label: 'System ready', chat_available: true, indexing_active: false,
  components: {}, index: { generation: 1, bm25_generation: 1, published_at: null, point_count: 1 },
  indexing: { worker_state: 'idle', worker_seen: true, worker_heartbeat_at: null, queue_depth: 0, queue_counts: {}, active_jobs: [], last_successful_index_at: null },
  models: { ollama: 'fixture', embedding: 'fixture', embedding_device: 'cpu', embedding_ready: true },
  gpu: { available: false, requested: false, device: 'cpu', utilization_percent: null, memory_used_mb: null, memory_total_mb: null },
  timestamps: { generated_at: new Date().toISOString(), worker_heartbeat_at: null, generation_published_at: null, last_successful_index_at: null },
  latency_ms: {}, lan_access: { enabled: false, mode: 'disabled', gateway_ready: false },
};

const checks = [];
const runtimeErrors = [];
const failedRequests = [];
const check = (name, condition, details = {}) => {
  assert.ok(condition, `${name}: ${JSON.stringify(details)}`);
  checks.push({ name, pass: true, ...details });
};

async function prepareContext(browser, options) {
  const context = await browser.newContext(options);
  await context.addInitScript(({ userId, metadataValue }) => {
    localStorage.setItem(`cial-ai-notice-ack:${userId}`, '1');
    sessionStorage.setItem('cial-auth-session-entry', userId);
    const scrollCalls = [];
    Object.defineProperty(window, '__motionScrollCalls', { value: scrollCalls, configurable: true });
    const nativeScrollTo = HTMLElement.prototype.scrollTo;
    HTMLElement.prototype.scrollTo = function instrumentedScrollTo(...args) {
      scrollCalls.push(args[0] && typeof args[0] === 'object' ? { ...args[0] } : { top: args[1] });
      return nativeScrollTo.apply(this, args);
    };
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input.url;
      if (!url.includes('/api/chat/stream')) return nativeFetch(input, init);
      const encoder = new TextEncoder();
      let index = 0;
      let answer = '';
      const stream = new ReadableStream({
        start(controller) {
          const timer = window.setInterval(() => {
            if (init?.signal?.aborted) {
              window.clearInterval(timer);
              controller.error(new DOMException('Aborted', 'AbortError'));
              return;
            }
            if (index < 70) {
              const delta = ` streamed-token-${index}`;
              answer += delta;
              controller.enqueue(encoder.encode(`${JSON.stringify({ request_id: 'fixture', type: 'token', stage_id: 'generation', status: 'started', elapsed_ms: index * 35, delta })}\n`));
              index += 1;
              return;
            }
            window.clearInterval(timer);
            controller.enqueue(encoder.encode(`${JSON.stringify({ request_id: 'fixture', type: 'result', stage_id: 'complete', status: 'completed', elapsed_ms: 2450, payload: { session_id: null, user_message_id: null, assistant_message_id: null, answer, citations: [], sources: [], metadata: metadataValue } })}\n`));
            controller.close();
          }, 35);
        },
      });
      return new Response(stream, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } });
    };
  }, { userId: user.id, metadataValue: metadata });
  await context.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/auth/me') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user, message: 'Authenticated.' }) });
    if (pathname === '/api/chat/sessions') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ sessions: [session] }) });
    if (pathname === '/api/system/status') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(systemStatus) });
    if (pathname === '/api/workspaces/me/notes') return route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[],"total":0}' });
    if (pathname === '/api/search/recent') return route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[]}' });
    if (pathname.includes('/file')) return route.fulfill({ status: 200, contentType: 'text/plain', body: 'Source preview fixture.' });
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
  return context;
}

async function dismissWelcome(page) {
  for (const name of ['Continue', 'I Understand']) {
    const button = page.getByRole('button', { name });
    if (await button.isVisible().catch(() => false)) await button.click();
  }
}

function instrumentPage(page) {
  page.on('pageerror', (error) => runtimeErrors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') runtimeErrors.push(message.text()); });
  page.on('requestfailed', (request) => {
    if (request.failure()?.errorText !== 'net::ERR_ABORTED') failedRequests.push({ url: request.url(), reason: request.failure()?.errorText });
  });
}

await mkdir(artifactDir, { recursive: true });
const browser = await chromium.launch({ headless: true });

try {
  const desktop = await prepareContext(browser, { viewport: { width: 1500, height: 900 }, reducedMotion: 'no-preference' });
  const page = await desktop.newPage();
  instrumentPage(page);
  await page.goto(`${baseURL}/assistant/conversations/${sessionId}`);
  await dismissWelcome(page);
  await page.waitForTimeout(500);
  if (await page.getByTestId('chat-messages').count() === 0) {
    throw new Error(`Assistant fixture did not render: ${JSON.stringify({ url: page.url(), runtimeErrors, text: (await page.locator('body').innerText()).slice(0, 600) })}`);
  }
  await page.getByTestId('chat-messages').waitFor();
  await page.getByTestId('conversation-history-sidebar').waitFor();

  const historyMotion = await page.getByTestId('conversation-history-sidebar').evaluate((element) => {
    const style = getComputedStyle(element);
    return { property: style.transitionProperty, duration: style.transitionDuration };
  });
  check('desktop History uses scoped reversible panel motion', historyMotion.property.includes('opacity') && historyMotion.property.includes('transform') && !historyMotion.property.includes('width') && historyMotion.duration.includes('0.22s'), historyMotion);
  await page.getByTestId('button-collapse-history-sidebar').click();
  await page.getByTestId('button-sidebar-open-history').click();
  await page.waitForFunction(() => document.querySelector('[data-testid="conversation-history-sidebar"]')?.getAttribute('data-state') === 'open');
  check('desktop History rapidly reverses without detach', await page.getByTestId('conversation-history-sidebar').count() === 1);
  await page.getByTestId('button-collapse-history-sidebar').click();
  await page.getByTestId('conversation-history-sidebar').waitFor({ state: 'detached' });
  check('desktop History exit restores focus', await page.getByTestId('button-sidebar-open-history').evaluate((element) => document.activeElement === element));
  await page.getByTestId('button-sidebar-open-history').click();

  const sourceToggle = page.getByTestId('button-toggle-sources').last();
  const sourceList = page.getByTestId('grouped-source-list').last();
  const closedHeight = await sourceList.evaluate((element) => element.getBoundingClientRect().height);
  await sourceToggle.click();
  await page.waitForTimeout(240);
  const openHeight = await sourceList.evaluate((element) => element.getBoundingClientRect().height);
  check('source accordion animates variable content without fixed height', openHeight > closedHeight + 80 && await sourceList.getAttribute('data-state') === 'open', { closedHeight, openHeight });
  await sourceToggle.click();
  await sourceToggle.click();
  await page.waitForTimeout(240);
  check('source accordion supports rapid reversal', await sourceList.getAttribute('data-state') === 'open');

  await page.getByTestId('button-open-source-1').last().click();
  const resizeHandle = page.getByTestId('assistant-source-resize-handle');
  await resizeHandle.waitFor();
  const beforeHandle = await resizeHandle.boundingBox();
  await page.mouse.move(beforeHandle.x + beforeHandle.width / 2, beforeHandle.y + beforeHandle.height / 2);
  await page.mouse.down();
  await page.mouse.move(beforeHandle.x - 90, beforeHandle.y + beforeHandle.height / 2, { steps: 2 });
  const duringResize = await resizeHandle.boundingBox();
  check('assistant resize tracks pointer with no panel geometry transition', Math.abs(duringResize.x - beforeHandle.x) > 40 && await page.getByTestId('assistant-source-panel-group').getAttribute('data-resizing') === 'true', { beforeX: beforeHandle.x, duringX: duringResize.x });
  await page.mouse.up();
  await page.getByRole('button', { name: 'Close source drawer' }).click().catch(() => page.getByRole('button', { name: /Close source/i }).click());

  const messages = page.getByTestId('chat-messages');
  await messages.evaluate((element) => { element.scrollTop = element.scrollHeight; element.dispatchEvent(new Event('scroll')); });
  await page.getByTestId('input-chat').fill('Verify streamed follow behavior');
  await page.getByTestId('button-send').click();
  await page.waitForFunction(() => document.querySelector('[data-testid="chat-messages"]')?.textContent?.includes('streamed-token-5'));
  await messages.evaluate((element) => { element.scrollTop = 0; element.dispatchEvent(new Event('scroll')); });
  const callsBeforePause = await page.evaluate(() => window.__motionScrollCalls.length);
  await page.waitForTimeout(500);
  const pausedState = await messages.evaluate((element) => ({ top: element.scrollTop, distance: element.scrollHeight - element.scrollTop - element.clientHeight }));
  const callsAfterPause = await page.evaluate(() => window.__motionScrollCalls.length);
  check('manual upward scrolling suspends streamed auto-follow', pausedState.top < 20 && callsAfterPause === callsBeforePause, { pausedState, callsBeforePause, callsAfterPause });
  await messages.evaluate((element) => { element.scrollTop = element.scrollHeight; element.dispatchEvent(new Event('scroll')); });
  const callsBeforeResume = await page.evaluate(() => window.__motionScrollCalls.length);
  await page.waitForTimeout(500);
  const resumedState = await messages.evaluate((element) => ({ distance: element.scrollHeight - element.scrollTop - element.clientHeight }));
  const scrollCalls = await page.evaluate(() => window.__motionScrollCalls);
  check('returning near bottom resumes follow without smooth-scroll restarts', resumedState.distance <= 96 && scrollCalls.length > callsBeforeResume && scrollCalls.every((call) => call.behavior !== 'smooth'), { resumedState, calls: scrollCalls.length });

  const appearance = page.getByTestId('appearance-toggle-expanded');
  const appearanceMotion = await appearance.evaluate((element) => {
    const thumb = getComputedStyle(element.querySelector('.appearance-toggle-thumb'));
    const option = getComputedStyle(element.querySelector('.appearance-option'));
    return { thumbDuration: thumb.transitionDuration, thumbTiming: thumb.transitionTimingFunction, optionDuration: option.transitionDuration };
  });
  check('Appearance thumb and state feedback are synchronized', appearanceMotion.thumbDuration.split(', ').every((value) => value === '0.18s') && appearanceMotion.optionDuration.split(', ').every((value) => value === '0.18s') && appearanceMotion.thumbTiming.includes('cubic-bezier(0.77, 0, 0.175, 1)'), appearanceMotion);

  await page.goto(`${baseURL}/knowledge-graph`);
  const graphNodes = page.locator('[data-testid^="graph-node-"]');
  const graphTransition = await graphNodes.first().locator('circle').evaluate((element) => getComputedStyle(element).transitionProperty);
  const hoverStarted = Date.now();
  for (let index = 0; index < 36; index += 1) await graphNodes.nth(index % await graphNodes.count()).hover();
  check('Knowledge Graph repeated hover remains targeted and responsive', graphTransition.includes('transform') && !/(all|stroke|filter)/.test(graphTransition) && Date.now() - hoverStarted < 5000, { graphTransition, elapsedMs: Date.now() - hoverStarted });

  await page.goto(`${baseURL}/faqs`);
  const popularArticle = page.locator('article').first();
  await popularArticle.hover();
  check('FAQ non-interactive article remains spatially static', await popularArticle.evaluate((element) => getComputedStyle(element).transform === 'none'));
  await desktop.close();

  const mobile = await prepareContext(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'no-preference' });
  const mobilePage = await mobile.newPage();
  instrumentPage(mobilePage);
  await mobilePage.goto(`${baseURL}/assistant/new`);
  await dismissWelcome(mobilePage);
  const opener = mobilePage.getByTestId('button-open-history-drawer');
  await opener.click();
  const drawer = mobilePage.getByTestId('history-drawer');
  await mobilePage.waitForFunction(() => document.querySelector('[data-testid="history-drawer"]')?.getAttribute('data-state') === 'open');
  check('mobile History opens from its right edge with coordinated backdrop', await drawer.evaluate((element) => {
    const panel = element.lastElementChild;
    return getComputedStyle(panel).transitionProperty.includes('transform') && getComputedStyle(element.firstElementChild).transitionProperty === 'opacity';
  }));
  await mobilePage.getByTestId('button-close-history-drawer-icon').click();
  await opener.click();
  await mobilePage.waitForFunction(() => document.querySelector('[data-testid="history-drawer"]')?.getAttribute('data-state') === 'open');
  check('mobile History rapid reversal keeps one drawer', await drawer.count() === 1);
  await mobilePage.keyboard.press('Escape');
  await drawer.waitFor({ state: 'detached' });
  check('mobile History Escape restores focus and releases scroll lock', await opener.evaluate((element) => document.activeElement === element && document.body.style.overflow === ''));
  await opener.click();
  await mobilePage.getByRole('button', { name: 'Close history drawer' }).first().click({ position: { x: 12, y: 400 } });
  await drawer.waitFor({ state: 'detached' });
  await opener.click();
  await mobilePage.goto(`${baseURL}/faqs`);
  check('mobile route change removes drawer, backdrop, and lock', await mobilePage.getByTestId('history-drawer').count() === 0 && await mobilePage.evaluate(() => document.body.style.overflow === ''));
  await mobile.close();

  const reduced = await prepareContext(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' });
  const reducedPage = await reduced.newPage();
  instrumentPage(reducedPage);
  await reducedPage.goto(`${baseURL}/assistant/new`);
  await dismissWelcome(reducedPage);
  await reducedPage.getByTestId('button-open-history-drawer').click();
  const reducedDrawer = reducedPage.getByTestId('history-drawer');
  await reducedPage.waitForFunction(() => document.querySelector('[data-testid="history-drawer"]')?.getAttribute('data-state') === 'open');
  await reducedPage.getByTestId('button-close-history-drawer-icon').click();
  const reducedPanel = await reducedDrawer.evaluate((element) => {
    const style = getComputedStyle(element.lastElementChild);
    return { transform: style.transform, property: style.transitionProperty, duration: style.transitionDuration };
  });
  check('reduced motion removes panel translation and universal clamp', reducedPanel.transform === 'none' && reducedPanel.property === 'opacity' && reducedPanel.duration === '0.14s', reducedPanel);
  await reducedDrawer.waitFor({ state: 'detached' });
  await reducedPage.getByTestId('button-hamburger').click();
  await reducedPage.getByTestId('mobile-sidebar').waitFor({ state: 'visible' });
  const reducedAppearance = await reducedPage.getByTestId('appearance-toggle-mobile').evaluate((element) => ({
    thumb: getComputedStyle(element.querySelector('.appearance-toggle-thumb')).transitionDuration,
    option: getComputedStyle(element.querySelector('.appearance-option')).transitionDuration,
  }));
  check('reduced motion preserves useful non-spatial Appearance feedback', reducedAppearance.thumb === '0s' && reducedAppearance.option.split(', ').every((value) => value === '0.18s'), reducedAppearance);
  await reduced.close();

  check('no uncaught exceptions or unexpected console errors', runtimeErrors.length === 0, { runtimeErrors });
  check('no unexpected failed requests', failedRequests.length === 0, { failedRequests });
} finally {
  await browser.close();
}

const result = { generatedAt: new Date().toISOString(), baseURL, checks, runtimeErrors, failedRequests, overall: 'pass' };
await writeFile(path.join(artifactDir, 'verification-result.json'), `${JSON.stringify(result, null, 2)}\n`, 'utf8');
console.log(JSON.stringify({ overall: result.overall, checks: checks.length, artifactDir }, null, 2));
