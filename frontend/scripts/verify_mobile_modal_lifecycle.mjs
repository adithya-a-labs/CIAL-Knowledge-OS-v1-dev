import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const baseURL = (process.env.CIAL_MOBILE_TEST_URL || 'http://127.0.0.1:4174').replace(/\/$/, '');
const documentId = process.env.CIAL_MOBILE_TEST_DOCUMENT_ID || '0873aa81-7e14-4449-bae7-e5436b24dc67';
const user = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'playwright@cial.in',
  display_name: 'Playwright Mobile',
  initials: 'PM',
  organization_name: 'CIAL',
  department_name: 'Validation',
  role_names: ['viewer'],
  permission_names: [],
  notifications_count: 0,
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 768, height: 1024 },
  deviceScaleFactor: 2,
  hasTouch: true,
  isMobile: true,
  userAgent: 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
});
let authenticated = false;

await context.addInitScript(({ userId }) => {
  localStorage.setItem(`cial-ai-notice-ack:${userId}`, '1');
}, { userId: user.id });
await context.route('**/api/auth/me', async (route) => {
  await route.fulfill(authenticated
    ? { status: 200, contentType: 'application/json', body: JSON.stringify({ user, message: 'Authenticated.' }) }
    : { status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Authentication required.' }) });
});
await context.route('**/api/auth/login', async (route) => {
  authenticated = true;
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user, message: 'Logged in successfully.' }) });
});
await context.route('**/api/auth/logout', async (route) => {
  authenticated = false;
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Logged out.' }) });
});
await context.route('**/api/chat/sessions', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"sessions":[]}' }));
await context.route('**/api/workspaces/me/notes?filter=recent', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[],"total":0}' }));
await context.route('**/api/search/recent', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[]}' }));
await context.route('**/api/documents/*/analysis?**', (route) => route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"No saved analysis fixture."}' }));

const page = await context.newPage();
const state = () => page.evaluate(() => {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const elements = Array.from(document.querySelectorAll('*'));
  return {
    bodyOverflow: document.body.style.overflow,
    bodyComputedOverflow: getComputedStyle(document.body).overflow,
    bodyPointerEvents: document.body.style.pointerEvents,
    bodyComputedPointerEvents: getComputedStyle(document.body).pointerEvents,
    bodyScrollLocked: document.body.getAttribute('data-scroll-locked'),
    htmlOverflow: document.documentElement.style.overflow,
    htmlPointerEvents: document.documentElement.style.pointerEvents,
    htmlScrollLocked: document.documentElement.getAttribute('data-scroll-locked'),
    inertCount: elements.filter((element) => element.hasAttribute('inert')).length,
    hiddenModalCount: elements.filter((element) => (element.getAttribute('role') === 'dialog' || element.getAttribute('aria-modal') === 'true') && !visible(element)).length,
    visibleModalCount: elements.filter((element) => (element.getAttribute('role') === 'dialog' || element.getAttribute('aria-modal') === 'true') && visible(element)).length,
    invisibleFullscreenOverlayCount: elements.filter((element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const fullscreen = style.position === 'fixed' && rect.left <= 1 && rect.top <= 1
        && rect.right >= innerWidth - 1 && rect.bottom >= innerHeight - 1;
      return fullscreen && !visible(element);
    }).length,
    mobileSidebarCount: document.querySelectorAll('[data-testid="mobile-sidebar"]').length,
    corpusOverlayCount: document.querySelectorAll('[data-testid="corpus-tree-overlay"]').length,
    assistantOverlayCount: document.querySelectorAll('[data-testid="document-assistant-overlay"]').length,
  };
});
const waitForClean = async (label) => {
  await page.waitForFunction(() => {
    const hiddenModal = Array.from(document.querySelectorAll('[role="dialog"], [aria-modal="true"]')).some((element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0;
    });
    return !hiddenModal && !document.querySelector('[data-testid="mobile-sidebar"]')
      && document.body.style.overflow === '' && document.body.style.pointerEvents === ''
      && !document.body.hasAttribute('data-scroll-locked');
  });
  const value = await state();
  assert.equal(value.bodyOverflow, '', `${label}: body overflow`);
  assert.equal(value.bodyPointerEvents, '', `${label}: body pointer-events`);
  assert.equal(value.bodyComputedPointerEvents, 'auto', `${label}: computed pointer-events`);
  assert.equal(value.bodyScrollLocked, null, `${label}: body data-scroll-locked`);
  assert.equal(value.htmlOverflow, '', `${label}: html overflow`);
  assert.equal(value.htmlPointerEvents, '', `${label}: html pointer-events`);
  assert.equal(value.htmlScrollLocked, null, `${label}: html data-scroll-locked`);
  assert.equal(value.inertCount, 0, `${label}: inert elements`);
  assert.equal(value.hiddenModalCount, 0, `${label}: hidden modal`);
  assert.equal(value.invisibleFullscreenOverlayCount, 0, `${label}: invisible overlay`);
  return value;
};

try {
  await page.goto(`${baseURL}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForURL('**/login');
  await waitForClean('portrait login initial load');
  await page.getByLabel('Email Address').fill('playwright@cial.in');
  await page.getByTestId('login-password').fill('frontend-only-fixture');
  await page.getByRole('button', { name: 'Log In' }).click();
  await page.waitForURL(`${baseURL}/`);
  const continueButton = page.getByRole('button', { name: 'Continue' });
  if (await continueButton.isVisible().catch(() => false)) await continueButton.click();
  await waitForClean('login complete');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForClean('portrait refresh');
  await page.getByTestId('button-hamburger').click();
  await page.getByTestId('mobile-sidebar').waitFor({ state: 'visible' });
  const navigationMotion = await page.getByTestId('mobile-sidebar').evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      duration: style.animationDuration,
      timing: style.animationTimingFunction,
      name: style.animationName,
    };
  });
  assert.equal(navigationMotion.duration, '0.22s', 'global navigation uses the shared panel duration');
  assert.equal(
    navigationMotion.timing,
    'cubic-bezier(0.32, 0.72, 0, 1)',
    'global navigation uses the shared drawer easing',
  );
  assert.notEqual(navigationMotion.name, 'none', 'global navigation preserves spatial continuity');
  assert.equal((await state()).visibleModalCount, 1, 'global navigation owns the only modal');
  const openNavigationState = await state();
  assert.ok(
    openNavigationState.bodyComputedOverflow === 'hidden' || openNavigationState.bodyScrollLocked !== null,
    'open navigation owns scroll lock',
  );
  await page.getByTestId('button-close-sidebar').click();
  await waitForClean('global navigation close');

  await page.getByTestId('button-hamburger').click();
  await page.keyboard.press('Control+K');
  assert.equal((await state()).visibleModalCount, 1, 'Ctrl+K cannot stack a second modal');
  await page.getByRole('button', { name: /Search Ctrl\+K/ }).click();
  await page.getByRole('textbox', { name: 'Global search' }).waitFor({ state: 'visible' });
  assert.equal((await state()).visibleModalCount, 1, 'search handoff has one modal owner');
  await page.keyboard.press('Escape');
  await waitForClean('search close');

  await page.getByTestId('button-hamburger').click();
  await page.getByRole('link', { name: 'Knowledge Center' }).click();
  await page.waitForURL('**/knowledge-center');
  await waitForClean('route change with sheet open');

  await page.goto(`${baseURL}/`);
  await page.getByTestId('button-hamburger').click();
  await page.setViewportSize({ width: 1024, height: 768 });
  await waitForClean('portrait to landscape');
  assert.equal((await state()).mobileSidebarCount, 0, 'landscape has no mobile sidebar');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForClean('landscape initial load');
  const main = page.getByTestId('main-content');
  await main.evaluate((element) => { element.scrollTop = 220; });
  assert.ok(await main.evaluate((element) => element.scrollTop > 0), 'background scroll is restored');

  await page.setViewportSize({ width: 768, height: 1024 });
  await waitForClean('landscape to portrait');
  await page.goto(`${baseURL}/knowledge/document/${documentId}`);
  await page.getByRole('button', { name: 'Toggle corpus tree' }).waitFor();
  await page.getByRole('button', { name: 'Toggle corpus tree' }).click();
  await page.getByTestId('corpus-tree-panel').waitFor({ state: 'visible' });
  await page.getByRole('button', { name: 'Close corpus tree' }).click();
  await page.getByTestId('corpus-tree-panel').waitFor({ state: 'detached' });
  assert.equal((await state()).corpusOverlayCount, 0, 'Corpus Tree overlay is removed');
  await page.getByRole('button', { name: 'Toggle document assistant' }).click();
  await page.getByTestId('document-assistant-panel').waitFor({ state: 'visible' });
  await page.getByRole('button', { name: 'Close document assistant' }).click();
  await page.getByTestId('document-assistant-panel').waitFor({ state: 'detached' });
  assert.equal((await state()).assistantOverlayCount, 0, 'Document Assistant overlay is removed');
  await waitForClean('document mobile panels closed');

  await page.goto(`${baseURL}/`);
  await page.getByTestId('button-hamburger').click();
  await page.getByRole('button', { name: 'Log Out' }).click();
  await page.waitForURL('**/login');
  await waitForClean('logout');

  console.log(JSON.stringify({
    result: 'PASS',
    baseURL,
    touch: true,
    scenarios: [
      'iPad portrait initial/login/refresh',
      'shared 220ms drawer timing and easing',
      'global navigation close/search handoff/route change',
      'portrait-landscape-portrait',
      'Corpus Tree and Document Assistant close',
      'body overflow/pointer-events/data-scroll-locked/inert/overlay cleanup',
      'logout',
    ],
  }));
} finally {
  await context.close();
  await browser.close();
}
