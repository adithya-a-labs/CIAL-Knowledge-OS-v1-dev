import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..');
const requireFromFrontend = createRequire(path.join(repoRoot, 'frontend', 'package.json'));
const { chromium } = requireFromFrontend('playwright');

const baseUrl = (process.env.CIAL_FRONTEND_URL ?? 'http://127.0.0.1:5173').replace(/\/$/, '');
const configuredOutputDir = process.env.CIAL_DARK_MODE_OUTPUT_DIR;
const outputDir = configuredOutputDir
  ? path.resolve(repoRoot, configuredOutputDir)
  : path.join(repoRoot, 'outputs', 'playwright', 'dark-mode');
await fs.mkdir(outputDir, { recursive: true });

const result = {
  startedAt: new Date().toISOString(),
  baseUrl,
  defaultSystemModePassed: false,
  explicitDarkPassed: false,
  explicitLightPassed: false,
  explicitSystemPassed: false,
  persistencePassed: false,
  routePersistencePassed: false,
  collapsedSidebarPassed: false,
  mobileDrawerPassed: false,
  keyboardNavigationPassed: false,
  assistantPassed: false,
  assistantAnswerAttempted: false,
  assistantMarkdownPassed: false,
  assistantCitationsPassed: false,
  knowledgeCenterPassed: false,
  documentViewerPassed: false,
  workspacePassed: false,
  savedKnowledgePassed: false,
  summaryWorkspacePassed: false,
  adminPassed: false,
  portalThemePassed: false,
  noThemeFlashPassed: false,
  authThemePersistencePassed: false,
  surfaceSanityPassed: false,
  botanicalHierarchyPassed: false,
  routeResults: {},
  activeTheme: null,
  localStoragePreference: null,
  computedColors: {},
  consoleErrors: [],
  consoleWarnings: [],
  failedRequests: [],
  unexpectedConsoleErrors: [],
  unexpectedFailedRequests: [],
  apiResponses: [],
  screenshots: {},
  exceptions: [],
  requiredFailures: [],
};

function recordFailure(name, detail) {
  result.requiredFailures.push({ name, detail });
}

function requireAssertion(name, condition, detail) {
  if (!condition) recordFailure(name, detail);
  return Boolean(condition);
}

function relativeArtifact(file) {
  return path.relative(repoRoot, file).replaceAll('\\', '/');
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 950 },
  colorScheme: 'light',
  reducedMotion: 'reduce',
});
const page = await context.newPage();

page.on('console', (message) => {
  const entry = { route: new URL(page.url()).pathname, type: message.type(), text: message.text() };
  if (message.type() === 'error') result.consoleErrors.push(entry);
  if (message.type() === 'warning') result.consoleWarnings.push(entry);
});
page.on('requestfailed', (request) => {
  result.failedRequests.push({
    route: new URL(page.url()).pathname,
    url: request.url(),
    method: request.method(),
    failure: request.failure()?.errorText ?? 'unknown',
  });
});
page.on('response', (response) => {
  if (!response.url().includes('/api/')) return;
  result.apiResponses.push({
    route: new URL(page.url()).pathname,
    url: response.url(),
    method: response.request().method(),
    status: response.status(),
  });
});

async function screenshot(name, options = {}) {
  const file = path.join(outputDir, name);
  await page.screenshot({ path: file, fullPage: true, ...options });
  result.screenshots[name.replace(/\.png$/, '')] = relativeArtifact(file);
  return file;
}

async function goto(route, { protectedRoute = true } = {}) {
  await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  if (protectedRoute) {
    await page.waitForSelector('main, [data-testid="login-submit"]', { timeout: 60_000 });
  }
  await page.waitForTimeout(350);
}

async function themeState() {
  return page.evaluate(() => ({
    htmlClass: document.documentElement.className,
    storedTheme: localStorage.getItem('cial-theme'),
    colorScheme: getComputedStyle(document.documentElement).colorScheme,
    bodyBackground: getComputedStyle(document.body).backgroundColor,
    bodyColor: getComputedStyle(document.body).color,
  }));
}

async function surfaceAudit(route) {
  const audit = await page.evaluate(() => {
    const isVisible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width >= 40 &&
        rect.height >= 30 &&
        rect.bottom > 0 &&
        rect.right > 0 &&
        rect.top < innerHeight &&
        rect.left < innerWidth &&
        style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        Number(style.opacity) !== 0
      );
    };
    const intentionalPaper = (element) =>
      element.matches('canvas, img') ||
      Boolean(element.closest('.document-paper, .react-pdf__Page, [data-theme-paper="true"]'));
    const white = [...document.querySelectorAll('*')]
      .filter((element) => isVisible(element))
      .filter((element) => getComputedStyle(element).backgroundColor === 'rgb(255, 255, 255)')
      .map((element) => ({
        tag: element.tagName,
        testid: element.getAttribute('data-testid'),
        className: String(element.className).slice(0, 180),
        intentionalPaper: intentionalPaper(element),
      }));
    return {
      bodyBackground: getComputedStyle(document.body).backgroundColor,
      bodyColor: getComputedStyle(document.body).color,
      textLength: document.body.innerText.trim().length,
      white,
      unexpectedWhite: white.filter((entry) => !entry.intentionalPaper),
    };
  });
  result.routeResults[route] = { ...(result.routeResults[route] ?? {}), surface: audit };
  return audit;
}

async function openAppearance() {
  const trigger = page
    .locator(
      '[data-testid="appearance-trigger"]:visible, [data-testid="appearance-trigger-collapsed"]:visible',
    )
    .first();
  await trigger.waitFor({ state: 'visible', timeout: 15_000 });
  await trigger.click();
  await page.getByTestId('appearance-menu').waitFor({ state: 'visible' });
  return trigger;
}

async function chooseAppearance(mode) {
  await openAppearance();
  await page.getByTestId(`appearance-option-${mode}`).click();
  await page.waitForTimeout(100);
}

async function routeCheck(route, name, screenshotName, testid) {
  await goto(route);
  if (testid) {
    await page.locator(`[data-testid="${testid}"]`).first().waitFor({ state: 'visible', timeout: 30_000 });
  }
  const state = await themeState();
  const surface = await surfaceAudit(route);
  const passed =
    state.htmlClass.split(/\s+/).includes('dark') &&
    state.storedTheme === 'dark' &&
    state.bodyBackground === 'rgb(0, 0, 0)' &&
    surface.textLength > 20 &&
    surface.unexpectedWhite.length === 0;
  result.routeResults[route] = {
    ...(result.routeResults[route] ?? {}),
    passed,
    activeTheme: state,
  };
  if (screenshotName) await screenshot(screenshotName);
  result[name] = passed;
  return passed;
}

try {
  // Default System mode: resolution must not create an explicit preference.
  await goto('/login', { protectedRoute: false });
  await page.evaluate(() => localStorage.removeItem('cial-theme'));
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="login-submit"]', { timeout: 30_000 });
  const systemLight = await themeState();
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await page.waitForFunction(() => document.documentElement.classList.contains('dark'));
  const systemDark = await themeState();
  result.defaultSystemModePassed = requireAssertion(
    'default-system-mode',
    !systemLight.htmlClass.includes('dark') &&
      systemLight.storedTheme === null &&
      systemDark.htmlClass.includes('dark') &&
      systemDark.storedTheme === null,
    { systemLight, systemDark },
  );

  // Create an isolated verification session through the product's supported auth flow.
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const email = process.env.CIAL_PLAYWRIGHT_EMAIL ?? `dark-mode-${suffix}@localhost.invalid`;
  const password = process.env.CIAL_PLAYWRIGHT_PASSWORD ?? `Cial!DarkMode${suffix}Aa1`;
  if (process.env.CIAL_PLAYWRIGHT_EMAIL && process.env.CIAL_PLAYWRIGHT_PASSWORD) {
    await goto('/login', { protectedRoute: false });
    await page.getByTestId('login-email').fill(email);
    await page.getByTestId('login-password').fill(password);
    await page.getByTestId('login-submit').click();
  } else {
    await goto('/signup', { protectedRoute: false });
    await page.getByTestId('signup-name').fill('Dark Mode Verification');
    await page.getByTestId('signup-email').fill(email);
    await page.getByTestId('signup-password').fill(password);
    await page.getByTestId('signup-submit').click();
  }
  await page.waitForURL((url) => !['/login', '/signup'].includes(url.pathname), { timeout: 60_000 });
  const notice = page.getByRole('button', { name: 'I Understand' });
  if (await notice.isVisible().catch(() => false)) await notice.click();
  await goto('/');

  // Explicit Dark from the expanded sidebar.
  const expandedTrigger = page.getByTestId('appearance-trigger');
  await expandedTrigger.waitFor({ state: 'visible' });
  await chooseAppearance('dark');
  const explicitDark = await themeState();
  await openAppearance();
  const darkChecked = await page.getByTestId('appearance-option-dark').getAttribute('aria-checked');
  await page.keyboard.press('Escape');
  result.explicitDarkPassed = requireAssertion(
    'explicit-dark',
    explicitDark.htmlClass.includes('dark') &&
      explicitDark.storedTheme === 'dark' &&
      darkChecked === 'true',
    { explicitDark, darkChecked },
  );
  const botanicalTokens = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name) => style.getPropertyValue(name).trim();
    return {
      background: read('--background'),
      sidebar: read('--sidebar'),
      card: read('--card'),
      popover: read('--popover'),
      foreground: read('--foreground'),
      heading: read('--heading-foreground'),
      border: read('--border'),
      borderStrong: read('--border-strong'),
      primary: read('--primary'),
    };
  });
  result.botanicalHierarchyPassed = requireAssertion(
    'botanical-dark-hierarchy',
    botanicalTokens.background === '0 0% 0%' &&
      botanicalTokens.sidebar === '120 33% 1%' &&
      botanicalTokens.card === '120 17% 2%' &&
      botanicalTokens.popover === '108 24% 4%' &&
      botanicalTokens.foreground === '90 20% 96%' &&
      botanicalTokens.heading === '0 0% 100%' &&
      botanicalTokens.border === '109 18% 12%' &&
      botanicalTokens.borderStrong === '113 18% 19%' &&
      botanicalTokens.primary === '103 47% 56%',
    botanicalTokens,
  );
  await screenshot('dark-dashboard.png');
  await screenshot('dark-sidebar-expanded.png');

  // Startup flash sampling after an explicit dark reload.
  await page.addInitScript(() => {
    window.__cialThemeFrames = [];
    let count = 0;
    const sample = () => {
      window.__cialThemeFrames.push({
        htmlClass: document.documentElement.className,
        htmlBackground: getComputedStyle(document.documentElement).backgroundColor,
        bodyBackground: document.body ? getComputedStyle(document.body).backgroundColor : null,
      });
      count += 1;
      if (count < 12) requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('main', { timeout: 60_000 });
  await page.waitForTimeout(300);
  const flashFrames = await page.evaluate(() => window.__cialThemeFrames ?? []);
  result.routeResults.themeFlashFrames = flashFrames;
  result.noThemeFlashPassed = requireAssertion(
    'no-theme-flash',
    flashFrames.length > 0 &&
      flashFrames.every(
        (frame) =>
          frame.htmlClass.includes('dark') &&
          frame.htmlBackground !== 'rgb(255, 255, 255)' &&
          frame.bodyBackground !== 'rgb(255, 255, 255)',
      ),
    flashFrames,
  );

  // Explicit Light while the emulated OS remains dark.
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await chooseAppearance('light');
  const explicitLight = await themeState();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('main', { timeout: 60_000 });
  const explicitLightReload = await themeState();
  result.explicitLightPassed = requireAssertion(
    'explicit-light',
    !explicitLight.htmlClass.includes('dark') &&
      explicitLight.storedTheme === 'light' &&
      !explicitLightReload.htmlClass.includes('dark') &&
      explicitLightReload.storedTheme === 'light',
    { explicitLight, explicitLightReload },
  );

  // Explicit System must react to OS changes while retaining the System preference.
  await chooseAppearance('system');
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
  await page.waitForFunction(() => !document.documentElement.classList.contains('dark'));
  const explicitSystemLight = await themeState();
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await page.waitForFunction(() => document.documentElement.classList.contains('dark'));
  const explicitSystemDark = await themeState();
  await openAppearance();
  const systemChecked = await page.getByTestId('appearance-option-system').getAttribute('aria-checked');
  await page.keyboard.press('Escape');
  result.explicitSystemPassed = requireAssertion(
    'explicit-system',
    explicitSystemLight.storedTheme === 'system' &&
      !explicitSystemLight.htmlClass.includes('dark') &&
      explicitSystemDark.storedTheme === 'system' &&
      explicitSystemDark.htmlClass.includes('dark') &&
      systemChecked === 'true',
    { explicitSystemLight, explicitSystemDark, systemChecked },
  );

  // Return to explicit Dark for route and authentication persistence checks.
  await chooseAppearance('dark');
  const firstDocumentHref = await page
    .locator('a[href^="/knowledge/document/"]')
    .first()
    .getAttribute('href')
    .catch(() => null);

  const routeChecks = [
    ['/', 'surfaceSanityPassed', null, 'dashboard-page'],
    ['/assistant/new', 'assistantPassed', 'dark-assistant.png', 'assistant-workspace'],
    ['/knowledge-center', 'knowledgeCenterPassed', 'dark-knowledge-center.png', 'knowledge-center-page'],
    ['/workspace', 'workspacePassed', 'dark-workspace.png', 'workspace-page'],
    ['/saved-knowledge', 'savedKnowledgePassed', 'dark-saved-knowledge.png', 'workspace-page'],
    ['/workspace/summaries/new', 'summaryWorkspacePassed', 'dark-summary-workspace.png', 'summary-workspace'],
    ['/admin', 'adminPassed', 'dark-admin.png', null],
    ['/admin/system-monitor', 'adminPassed', 'dark-admin-system-monitor.png', null],
  ];
  for (const [route, key, shot, testid] of routeChecks) {
    const passed = await routeCheck(route, key, shot, testid);
    if (!passed) recordFailure(`route-${route}`, result.routeResults[route]);
  }
  if (
    result.routeResults['/admin']?.surface?.textLength > 0 &&
    (await page.locator('text=Access Denied').count()) > 0
  ) {
    result.exceptions.push('Admin and System Monitor visual coverage used the role-gated Access Denied state.');
  }

  // Find and validate a real document route.
  let documentRoute = firstDocumentHref;
  if (!documentRoute) {
    await goto('/knowledge-center');
    documentRoute = await page
      .locator('a[href^="/knowledge/document/"]')
      .first()
      .getAttribute('href')
      .catch(() => null);
  }
  if (documentRoute) {
    result.documentViewerPassed = await routeCheck(
      documentRoute,
      'documentViewerPassed',
      'dark-document-viewer.png',
      null,
    );
    const paperCount = await page
      .locator('.react-pdf__Page, .document-paper, canvas')
      .count()
      .catch(() => 0);
    result.routeResults[documentRoute].intentionalPaperSurfaceCount = paperCount;
  } else {
    result.exceptions.push('No authorized real document route was available for the document viewer.');
    recordFailure('document-viewer-route', 'No authorized document link was available.');
  }

  // Route/reload persistence.
  await goto('/knowledge-center');
  const routeDark = await themeState();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="knowledge-center-page"]', { timeout: 60_000 });
  const reloadDark = await themeState();
  result.persistencePassed = requireAssertion(
    'dark-reload-persistence',
    reloadDark.htmlClass.includes('dark') && reloadDark.storedTheme === 'dark',
    reloadDark,
  );
  result.routePersistencePassed = requireAssertion(
    'dark-route-persistence',
    routeDark.htmlClass.includes('dark') &&
      routeDark.storedTheme === 'dark' &&
      reloadDark.htmlClass.includes('dark'),
    { routeDark, reloadDark },
  );

  // Command palette is a Radix portal/dialog and must inherit the root theme.
  await page.keyboard.press('Control+K');
  const commandDialog = page.getByRole('dialog').last();
  await commandDialog.waitFor({ state: 'visible', timeout: 15_000 });
  const portalColors = await commandDialog.evaluate((element) => {
    const style = getComputedStyle(element);
    return { background: style.backgroundColor, color: style.color };
  });
  const portalThemeState = await themeState();
  result.portalThemePassed = requireAssertion(
    'portal-theme',
    portalColors.background !== 'rgb(255, 255, 255)' &&
      portalThemeState.colorScheme !== 'light',
    { portalColors, portalThemeState },
  );
  await screenshot('dark-command-palette.png');
  await page.keyboard.press('Escape');

  // Exercise the live assistant path when runtime dependencies permit it.
  await goto('/assistant/new');
  const composer = page.getByTestId('input-chat');
  const send = page.getByTestId('button-send');
  const composerFile = path.join(outputDir, 'dark-assistant-composer.png');
  await page.getByTestId('chat-panel').screenshot({ path: composerFile });
  result.screenshots.darkAssistantComposer = relativeArtifact(composerFile);
  await composer.fill('Give a short markdown checklist for verifying indexed documents.');
  if (!(await send.isDisabled().catch(() => true))) {
    result.assistantAnswerAttempted = true;
    await send.click();
    const answer = page.getByTestId('assistant-markdown').last();
    const assistantError = page.getByTestId('assistant-error');
    await Promise.race([
      answer.waitFor({ state: 'visible', timeout: 120_000 }),
      assistantError.waitFor({ state: 'visible', timeout: 120_000 }),
    ]).catch(() => {});
    result.assistantMarkdownPassed = await answer.isVisible().catch(() => false);
    result.assistantCitationsPassed =
      (await page.locator('[data-testid^="inline-citation-"], [data-testid="source-summary-accordion"]').count()) > 0;
    if (result.assistantMarkdownPassed) {
      await screenshot('dark-assistant-answer.png');
    } else {
      const errorText = await assistantError.textContent().catch(() => null);
      result.exceptions.push(
        `The live assistant answer could not be generated during visual verification${errorText ? `: ${errorText.trim()}` : '.'}`,
      );
    }
    if (result.assistantMarkdownPassed && !result.assistantCitationsPassed) {
      result.exceptions.push('The generated verification answer did not include a citation.');
    }
  } else {
    result.exceptions.push('The live assistant send control was disabled by runtime health, so answer/citation rendering was not exercised.');
  }

  // Collapsed sidebar geometry, tooltip, menu placement, and keyboard selection.
  await goto('/');
  await page.setViewportSize({ width: 1440, height: 950 });
  await page.getByTestId('button-toggle-global-navigation').click();
  const collapsedTrigger = page.getByTestId('appearance-trigger-collapsed');
  await collapsedTrigger.waitFor({ state: 'visible' });
  await collapsedTrigger.hover();
  await page.getByRole('tooltip', { name: 'Appearance' }).waitFor({ state: 'visible' });
  await screenshot('dark-sidebar-collapsed.png');
  await collapsedTrigger.focus();
  await page.keyboard.press('Enter');
  await page.getByTestId('appearance-menu').waitFor({ state: 'visible' });
  const menuBox = await page.getByTestId('appearance-menu').boundingBox();
  const darkOption = page.getByTestId('appearance-option-dark');
  await darkOption.focus();
  await page.keyboard.press('Space');
  const keyboardTheme = await themeState();
  result.keyboardNavigationPassed = requireAssertion(
    'appearance-keyboard',
    keyboardTheme.storedTheme === 'dark' &&
      (await collapsedTrigger.getAttribute('aria-label')) === 'Appearance: Dark',
    keyboardTheme,
  );
  result.collapsedSidebarPassed = requireAssertion(
    'collapsed-sidebar',
    Boolean(menuBox && menuBox.x >= 64 && menuBox.x + menuBox.width <= 1440) &&
      (await collapsedTrigger.isVisible()),
    menuBox,
  );

  // 1920 desktop and 1024 tablet coverage.
  await page.setViewportSize({ width: 1920, height: 1080 });
  await screenshot('dark-dashboard-1920.png');
  await page.setViewportSize({ width: 1024, height: 768 });
  await goto('/knowledge-center');
  await screenshot('dark-knowledge-center-tablet.png');

  // Mobile drawer focus trap, theme menu, Escape behavior, and focus restoration.
  await page.setViewportSize({ width: 390, height: 844 });
  await goto('/');
  const hamburger = page.getByTestId('button-hamburger');
  await hamburger.click();
  const drawer = page.getByTestId('mobile-sidebar');
  await drawer.waitFor({ state: 'visible' });
  const bodyLocked = await page.evaluate(() => document.body.style.overflow === 'hidden');
  await drawer.getByTestId('appearance-trigger').click();
  await page.getByTestId('appearance-option-dark').click();
  const drawerStayedOpen = await drawer.isVisible();
  await drawer.getByTestId('appearance-trigger').click();
  await page.keyboard.press('Escape');
  await page.getByTestId('appearance-menu').waitFor({ state: 'hidden', timeout: 5_000 }).catch(() => {});
  const menuClosedDrawerOpen =
    !(await page.getByTestId('appearance-menu').isVisible().catch(() => false)) &&
    (await drawer.isVisible());
  await screenshot('dark-mobile-drawer.png');
  await page.keyboard.press('Escape');
  const focusRestored = await hamburger.evaluate((element) => document.activeElement === element);
  result.mobileDrawerPassed = requireAssertion(
    'mobile-drawer',
    bodyLocked && drawerStayedOpen && menuClosedDrawerOpen && focusRestored,
    { bodyLocked, drawerStayedOpen, menuClosedDrawerOpen, focusRestored },
  );

  // Explicit Dark must survive logout and render before authentication.
  await page.setViewportSize({ width: 1440, height: 950 });
  await goto('/');
  await page.getByTestId('button-logout').click();
  await page.waitForURL(/\/login$/, { timeout: 30_000 });
  await page.waitForSelector('[data-testid="login-submit"]');
  const loggedOutTheme = await themeState();
  await screenshot('dark-login.png');
  result.authThemePersistencePassed = requireAssertion(
    'logout-login-theme-persistence',
    loggedOutTheme.htmlClass.includes('dark') &&
      loggedOutTheme.storedTheme === 'dark' &&
      loggedOutTheme.bodyBackground === 'rgb(0, 0, 0)',
    loggedOutTheme,
  );

  // Final global sanity fields.
  result.activeTheme = loggedOutTheme.htmlClass.includes('dark') ? 'dark' : 'light';
  result.localStoragePreference = loggedOutTheme.storedTheme;
  result.computedColors = loggedOutTheme;
  const darkRoutes = Object.entries(result.routeResults).filter(
    ([route, value]) => route.startsWith('/') && value?.surface,
  );
  result.surfaceSanityPassed = requireAssertion(
    'global-surface-sanity',
    darkRoutes.length >= 8 &&
      darkRoutes.every(
        ([, value]) =>
          value.surface.bodyBackground === 'rgb(0, 0, 0)' &&
          value.surface.unexpectedWhite.length === 0,
      ),
    darkRoutes,
  );

  result.unexpectedConsoleErrors = result.consoleErrors.filter(
    (entry) =>
      !(
        (entry.route === '/login' || entry.route === '/signup') &&
        entry.text.includes('401 (Unauthorized)')
      ),
  );
  result.unexpectedFailedRequests = result.failedRequests.filter(
    (entry) => entry.failure !== 'net::ERR_ABORTED',
  );
  if (result.unexpectedConsoleErrors.length) {
    recordFailure('console-errors', result.unexpectedConsoleErrors);
  }
  if (result.unexpectedFailedRequests.length) {
    recordFailure('failed-requests', result.unexpectedFailedRequests);
  }
} catch (error) {
  recordFailure('verification-runner', error instanceof Error ? error.stack ?? error.message : String(error));
} finally {
  result.completedAt = new Date().toISOString();
  result.passed = result.requiredFailures.length === 0;
  await fs.writeFile(
    path.join(outputDir, 'verification-result.json'),
    JSON.stringify(result, null, 2),
    'utf8',
  );
  await browser.close();
}

console.log(JSON.stringify(result, null, 2));
if (!result.passed) process.exitCode = 1;
