import { chromium } from "playwright";

const [url, expectedPage] = process.argv.slice(2);
if (!url || !expectedPage) {
  console.error("Usage: node verify-pdf-navigation.mjs <pdf-url> <page>");
  process.exit(2);
}

const expectedHash = `#page=${expectedPage}`;
const browser = await chromium.launch({ channel: "msedge", headless: false });
try {
  const page = await browser.newPage();
  await page.goto(`${url}${expectedHash}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.waitForTimeout(2_000);
  if (!page.url().endsWith(expectedHash)) {
    throw new Error(`Expected ${expectedHash}, received ${page.url()}`);
  }
  console.log(`Native PDF navigation retained exact page ${expectedPage}.`);
} finally {
  await browser.close();
}
