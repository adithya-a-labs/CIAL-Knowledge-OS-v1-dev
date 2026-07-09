import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const requireFromFrontend = createRequire(path.resolve('frontend/package.json'));
const { chromium } = requireFromFrontend('playwright');

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..');
const outputDir = path.join(repoRoot, 'outputs/playwright');
await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
const consoleMessages = [];
const failedRequests = [];
const apiCalls = [];

page.on('console', (message) => {
  if (['error', 'warning'].includes(message.type())) {
    consoleMessages.push({ type: message.type(), text: message.text() });
  }
});
page.on('requestfailed', (request) => {
  failedRequests.push({ url: request.url(), method: request.method(), failure: request.failure()?.errorText ?? 'unknown' });
});
page.on('response', (response) => {
  const url = response.url();
  if (url.includes('/api/')) {
    apiCalls.push({ url, method: response.request().method(), status: response.status() });
  }
});

const screenshot = async (name) => {
  const file = path.join(outputDir, name);
  await page.screenshot({ path: file, fullPage: true });
  return file;
};

const result = {
  appNotBlank: false,
  knowledgeCenterRealCorpus: false,
  folderOpened: false,
  documentSelected: false,
  assistantOpened: false,
  markdownVisible: false,
  citationsVisible: false,
  viewerOpened: false,
  responseModePayload: false,
  chatRequestStatus: null,
  screenshots: {},
  consoleMessages,
  failedRequests,
  apiCalls,
};

await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle', timeout: 60000 });
result.appNotBlank = (await page.locator('body').innerText()).trim().length > 0;

await page.goto('http://127.0.0.1:5173/knowledge-center', { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForSelector('[data-testid="knowledge-center-page"]', { timeout: 30000 });
result.screenshots.knowledgeCenter = await screenshot('knowledge-center.png');
const bodyText = await page.locator('body').innerText();
result.knowledgeCenterRealCorpus = bodyText.includes('Corpus Tree') && !bodyText.includes('Demo data is shown');

const firstFolder = page.locator('article').filter({ hasText: /files|Root|Guidelines|CERT/i }).first();
if (await firstFolder.count()) {
  await firstFolder.click();
  await page.waitForTimeout(1000);
  result.folderOpened = true;
}

const firstCheckbox = page.locator('[data-testid="knowledge-center-page"] input[type="checkbox"]').first();
if (await firstCheckbox.count()) {
  await firstCheckbox.check({ force: true });
  result.documentSelected = await firstCheckbox.isChecked();
}

const useAssistant = page.getByRole('button', { name: /Use in AI Assistant/i });
if (await useAssistant.count()) {
  await useAssistant.click();
  await page.waitForURL(/assistant/, { timeout: 15000 }).catch(() => {});
}
if (!page.url().includes('/assistant')) {
  await page.goto('http://127.0.0.1:5173/assistant', { waitUntil: 'networkidle', timeout: 60000 });
}
await page.waitForSelector('[data-testid="assistant-workspace"]', { timeout: 30000 });
result.assistantOpened = true;
result.markdownVisible = await page.locator('text=Grounded response').count() > 0;
result.citationsVisible = await page.locator('[data-testid^="citation-chip-"], [data-testid^="inline-citation-"]').count() > 0;

let capturedChatBody = null;
page.on('request', async (request) => {
  if (request.url().includes('/api/chat')) {
    capturedChatBody = request.postData();
  }
});

const modeButton = page.locator('[data-testid="select-response-length"] button').first();
if (await modeButton.count()) {
  await modeButton.click();
  await page.getByRole('radio', { name: /Quick/i }).click().catch(async () => {
    await page.keyboard.press('Escape');
  });
}

const input = page.locator('[data-testid="input-chat"]');
const sendButton = page.locator('[data-testid="button-send"]');
await input.fill('Give a short markdown checklist for verifying indexed documents.').catch(() => {});
if ((await sendButton.count()) && !(await sendButton.isDisabled().catch(() => true))) {
  const chatResponsePromise = page.waitForResponse((response) => response.url().includes('/api/chat'), { timeout: 90000 }).catch(() => null);
  await sendButton.click();
  const chatResponse = await chatResponsePromise;
  if (chatResponse) {
    result.chatRequestStatus = chatResponse.status();
  }
  await page.waitForTimeout(1000);
} else {
  result.chatRequestStatus = 'not_sent_send_disabled';
}
result.screenshots.chatAnswer = await screenshot('chat-answer.png');
result.responseModePayload = Boolean(capturedChatBody && capturedChatBody.includes('"response_length":"short"') && capturedChatBody.includes('"profile":"quick"'));
const chatCall = apiCalls.filter((call) => call.url.includes('/api/chat')).at(-1);
result.chatRequestStatus = chatCall?.status ?? result.chatRequestStatus;

result.citationsVisible = await page.locator('[data-testid^="citation-chip-"], [data-testid^="inline-citation-"]').count() > 0;
const sourceButton = page.locator('[data-testid^="button-open-source-"], [data-testid^="citation-chip-"], [data-testid^="inline-citation-"]').last();
if (await sourceButton.count()) {
  await sourceButton.click();
  await page.waitForTimeout(1500);
  result.viewerOpened = await page.locator('[data-testid="document-viewer-panel"], [data-testid="source-viewer-panel"]').count() > 0;
}
result.screenshots.citationViewer = await screenshot('citation-viewer.png');

await browser.close();

await fs.writeFile(path.join(outputDir, 'verification-result.json'), JSON.stringify(result, null, 2), 'utf-8');
console.log(JSON.stringify(result, null, 2));
