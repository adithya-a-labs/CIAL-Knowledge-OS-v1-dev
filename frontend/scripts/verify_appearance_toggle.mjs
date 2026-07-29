import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const artifactDir = path.resolve(frontendRoot, '..', 'outputs', 'playwright', 'appearance-toggle');
const baseUrl = process.env.CIAL_FRONTEND_URL ?? 'http://127.0.0.1:5173';
const checks = [];
const consoleErrors = [];
const failedRequests = [];
const expectedAbortedRequests = [];
const exceptions = [];

const check = (name, pass, details = {}) => {
  checks.push({ name, pass: Boolean(pass), ...details });
};

const waitForPreference = async (page, preference, resolvedClass) => {
  await page.waitForFunction(
    ({ expectedPreference, expectedClass }) =>
      localStorage.getItem('cial-theme') === expectedPreference
      && document.documentElement.classList.contains(expectedClass),
    { expectedPreference: preference, expectedClass: resolvedClass },
  );
};

const instrument = (page) => {
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => exceptions.push(error.message));
  page.on('requestfailed', (request) => {
    const failure = {
      url: request.url(),
      reason: request.failure()?.errorText ?? 'unknown',
    };
    if (failure.reason === 'net::ERR_ABORTED') {
      expectedAbortedRequests.push(failure);
    } else {
      failedRequests.push(failure);
    }
  });
};

await mkdir(artifactDir, { recursive: true });
const browser = await chromium.launch({ headless: true });

try {
  const bootstrapContext = await browser.newContext({
    viewport: { width: 1710, height: 902 },
    colorScheme: 'light',
  });
  const bootstrapPage = await bootstrapContext.newPage();
  instrument(bootstrapPage);
  await bootstrapPage.goto(`${baseUrl}/signup`);
  await bootstrapPage.getByTestId('signup-name').fill('Appearance Toggle Audit');
  await bootstrapPage.getByTestId('signup-email').fill(`appearance-${Date.now()}@example.com`);
  await bootstrapPage.getByTestId('signup-password').fill('AppearanceAudit2026!');
  await bootstrapPage.getByTestId('signup-submit').click();
  await bootstrapPage.waitForURL((url) => !url.pathname.endsWith('/signup'));
  const acknowledgeButton = bootstrapPage.getByRole('button', { name: 'I Understand' });
  if (await acknowledgeButton.isVisible()) await acknowledgeButton.click();
  await bootstrapPage.locator('.fixed.inset-0.z-\\[90\\]').waitFor({ state: 'detached' });
  const authenticatedState = await bootstrapContext.storageState();
  await bootstrapContext.close();

  const context = await browser.newContext({
    storageState: authenticatedState,
    viewport: { width: 1710, height: 902 },
    colorScheme: 'light',
    reducedMotion: 'no-preference',
  });
  const page = await context.newPage();
  instrument(page);
  await page.goto(baseUrl);
  await page.evaluate(() => localStorage.setItem('cial-theme', 'system'));
  await page.reload();
  await waitForPreference(page, 'system', 'light');

  const expanded = page.getByTestId('appearance-toggle-expanded');
  const expandedBox = await expanded.boundingBox();
  const expandedState = await expanded.evaluate((element) => {
    const track = element.querySelector('.appearance-toggle-track');
    const thumb = element.querySelector('.appearance-toggle-thumb');
    const selected = element.querySelector('[aria-checked="true"]');
    const trackStyle = getComputedStyle(track);
    const thumbStyle = getComputedStyle(thumb);
    return {
      orientation: track.getAttribute('aria-orientation'),
      selectedPreference: element.getAttribute('data-appearance-mode'),
      selectedName: selected?.getAttribute('aria-label'),
      track: {
        background: trackStyle.backgroundColor,
        borderColor: trackStyle.borderColor,
        height: track.getBoundingClientRect().height,
      },
      thumb: {
        background: thumbStyle.backgroundColor,
        borderColor: thumbStyle.borderColor,
        transform: thumbStyle.transform,
      },
    };
  });
  check('expanded 1710x902 geometry', expandedBox?.width === 215 && expandedBox?.height === 62, {
    box: expandedBox,
  });
  check('System remains the selected preference while resolved light', expandedState.selectedName === 'System', {
    state: expandedState,
  });

  await page.setViewportSize({ width: 1440, height: 950 });
  check('expanded 1440x950 has no horizontal overflow', await page.evaluate(
    () => document.documentElement.scrollWidth === document.documentElement.clientWidth,
  ));

  await page.getByTestId('appearance-toggle-expanded').getByRole('radio', { name: 'Dark' }).click();
  await waitForPreference(page, 'dark', 'dark');
  await page.reload();
  await waitForPreference(page, 'dark', 'dark');
  check('explicit Dark persists after reload', true);
  await page.goto(`${baseUrl}/knowledge-center`);
  await waitForPreference(page, 'dark', 'dark');
  check('preference persists across route navigation', true, { route: '/knowledge-center' });

  await page.goto(baseUrl);
  await page.getByTestId('button-toggle-global-navigation').click();
  const collapsed = page.getByTestId('appearance-toggle-collapsed');
  const collapsedBox = await collapsed.boundingBox();
  check('collapsed rail uses 40x114 vertical geometry', collapsedBox?.width === 40 && collapsedBox?.height === 114, {
    box: collapsedBox,
    orientation: await collapsed.getByRole('radio').first().evaluate(
      (element) => element.parentElement?.getAttribute('aria-orientation'),
    ),
  });
  await collapsed.getByRole('radio', { name: 'Dark' }).focus();
  await page.keyboard.press('ArrowUp');
  check('vertical ArrowUp selects and focuses System', await collapsed.getByRole('radio', { name: 'System' }).evaluate(
    (element) => element.getAttribute('aria-checked') === 'true' && document.activeElement === element,
  ));
  await page.evaluate(() => document.querySelector(
    '[data-testid="button-toggle-global-navigation"]',
  )?.click());
  check('focused option survives collapsed-to-expanded orientation change', await page.getByTestId(
    'appearance-toggle-expanded',
  ).getByRole('radio', { name: 'System' }).evaluate(
    (element) => element.getAttribute('aria-checked') === 'true' && document.activeElement === element,
  ));

  for (let index = 0; index < 4; index += 1) {
    await page.getByTestId('button-toggle-global-navigation').click();
  }
  check('repeated collapse/expand keeps one correctly selected option', await page.locator(
    '[data-testid^="appearance-toggle-"]:visible [aria-checked="true"]',
  ).count() === 1);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId('button-hamburger').click();
  const mobile = page.getByTestId('appearance-toggle-mobile');
  const labelsAt390 = await mobile.locator('.appearance-option-label').evaluateAll(
    (elements) => elements.map((element) => getComputedStyle(element).display),
  );
  await mobile.getByRole('radio', { name: 'Light' }).click();
  check('mobile 390px shows labels and selection keeps drawer open', labelsAt390.every(
    (display) => display !== 'none',
  ) && await page.getByTestId('mobile-sidebar').isVisible(), { labels: labelsAt390 });

  await page.setViewportSize({ width: 340, height: 844 });
  await page.waitForFunction(() => [...document.querySelectorAll(
    '[data-testid="appearance-toggle-mobile"] .appearance-option-label',
  )].every((element) => getComputedStyle(element).display === 'none'));
  const labelsAt340 = await mobile.locator('.appearance-option-label').evaluateAll(
    (elements) => elements.map((element) => getComputedStyle(element).display),
  );
  check('mobile 340px switches to icons-only without overflow', labelsAt340.every(
    (display) => display === 'none',
  ) && await page.evaluate(
    () => document.documentElement.scrollWidth === document.documentElement.clientWidth,
  ), { labels: labelsAt340 });
  await mobile.getByRole('radio', { name: 'Light' }).focus();
  await page.keyboard.press('End');
  await page.keyboard.press('ArrowLeft');
  check('horizontal Home/End/Arrow keyboard model selects System and preserves focus', await mobile.getByRole(
    'radio',
    { name: 'System' },
  ).evaluate((element) => element.getAttribute('aria-checked') === 'true' && document.activeElement === element));
  check('keyboard selection does not close mobile drawer', await page.getByTestId('mobile-sidebar').isVisible());
  await page.getByTestId('button-close-sidebar').click();
  check('mobile drawer close restores focus', await page.getByTestId('button-hamburger').evaluate(
    (element) => document.activeElement === element,
  ));

  await page.setViewportSize({ width: 1710, height: 902 });
  await page.emulateMedia({ colorScheme: 'light' });
  await page.evaluate(() => localStorage.setItem('cial-theme', 'system'));
  await page.reload();
  await waitForPreference(page, 'system', 'light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.waitForFunction(() => document.documentElement.classList.contains('dark'));
  check('System updates from resolved light to resolved dark while open', true);
  check('System remains visibly selected after OS change', await page.getByTestId(
    'appearance-toggle-expanded',
  ).getByRole('radio', { name: 'System' }).getAttribute('aria-checked') === 'true');
  await page.screenshot({
    path: path.join(artifactDir, 'system-resolved-dark.png'),
  });

  await context.close();

  const reducedContext = await browser.newContext({
    storageState: authenticatedState,
    viewport: { width: 1710, height: 902 },
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  });
  const reducedPage = await reducedContext.newPage();
  instrument(reducedPage);
  await reducedPage.goto(baseUrl);
  await reducedPage.evaluate(() => localStorage.setItem('cial-theme', 'system'));
  await reducedPage.reload();
  const reducedMotion = await reducedPage.getByTestId('appearance-toggle-expanded').locator(
    '.appearance-toggle-thumb',
  ).evaluate((element) => ({
    matches: matchMedia('(prefers-reduced-motion: reduce)').matches,
    duration: getComputedStyle(element).transitionDuration,
  }));
  check('reduced motion normalizes thumb movement', reducedMotion.matches && reducedMotion.duration.split(
    ',',
  ).every((duration) => Number.parseFloat(duration) <= 0.001), { reducedMotion });
  await reducedContext.close();
} catch (error) {
  exceptions.push(error instanceof Error ? error.stack ?? error.message : String(error));
} finally {
  await browser.close();
}

const unexpectedConsoleErrors = consoleErrors.filter(
  (message) => !message.includes('401 (Unauthorized)'),
);
check('no unexpected console errors', unexpectedConsoleErrors.length === 0, {
  errors: unexpectedConsoleErrors,
});
check('no failed network requests', failedRequests.length === 0, { failedRequests });
check('no Playwright exceptions', exceptions.length === 0, { exceptions });

const result = {
  generatedAt: new Date().toISOString(),
  baseUrl,
  routes: ['/', '/knowledge-center'],
  viewports: ['1710x902', '1440x950', '390x844', '340x844'],
  computedStyles: checks.find((item) => item.state)?.state ?? null,
  selectedPreference: 'system',
  resolvedTheme: 'dark',
  persistence: checks.find((item) => item.name.includes('reload'))?.pass ?? false,
  keyboard: checks.filter((item) => /Arrow|keyboard/.test(item.name)),
  responsive: checks.filter((item) => /geometry|mobile|overflow/.test(item.name)),
  reducedMotion: checks.find((item) => item.name.startsWith('reduced motion')) ?? null,
  consoleErrors: unexpectedConsoleErrors,
  failedRequests,
  expectedAbortedRequests,
  screenshots: [
    'before.png',
    'expanded-light.png',
    'expanded-dark.png',
    'collapsed-light.png',
    'collapsed-dark.png',
    'mobile-labelled.png',
    'mobile-icons-only.png',
    'system-resolved-dark.png',
  ],
  exceptions,
  checks,
  overall: checks.every((item) => item.pass) ? 'pass' : 'fail',
};

await writeFile(
  path.join(artifactDir, 'verification-result.json'),
  `${JSON.stringify(result, null, 2)}\n`,
  'utf8',
);

console.log(JSON.stringify({ overall: result.overall, checks: checks.length, artifactDir }, null, 2));
if (result.overall !== 'pass') process.exitCode = 1;
