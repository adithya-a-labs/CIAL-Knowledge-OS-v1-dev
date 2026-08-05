import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const panel = read('src/components/assistant/ChatPanel.tsx');
const message = read('src/components/assistant/ChatMessage.tsx');
const page = read('src/pages/AIAssistantPage.tsx');
const sourceViewer = read('src/components/assistant/SourceViewerPanel.tsx');
const sourceAccordion = read('src/components/assistant/SourceCitationCard.tsx');
const presence = read('src/components/assistant/useReversiblePresence.ts');
const highlightExcerpt = read('src/components/assistant/HighlightExcerpt.tsx');
const pdfViewer = read('src/components/assistant/renderers/PdfViewer.tsx');
const textViewer = read('src/components/assistant/renderers/TextViewer.tsx');
const spreadsheetViewer = read('src/components/assistant/renderers/SpreadsheetViewer.tsx');
const htmlViewer = read('src/components/assistant/renderers/HtmlViewer.tsx');

test('assistant streaming follows only while the reader remains near the bottom', () => {
  assert.match(panel, /CHAT_BOTTOM_THRESHOLD_PX = 96/);
  assert.match(panel, /distanceFromBottom <= CHAT_BOTTOM_THRESHOLD_PX/);
  assert.match(panel, /onScroll=\{\(event\) =>/);
  assert.match(panel, /if \(!viewport \|\| !autoFollowRef\.current\) return/);
  assert.match(panel, /viewport\.scrollTo\(\{ top: viewport\.scrollHeight, behavior: 'auto' \}\)/);
  assert.match(panel, /autoFollowRef\.current = true;\s+appendMessage\(requestSessionId, userMsg\)/);
  assert.doesNotMatch(panel, /scrollIntoView/);
  assert.doesNotMatch(panel, /behavior: 'smooth'/);
  assert.doesNotMatch(panel, /\[messages, isLoading, requestClock\]/);
});

test('source panel resizing tracks the handle without geometry transitions', () => {
  assert.match(panel, /onDragging=\{setSourcePanelResizing\}/);
  assert.match(panel, /data-resizing=\{sourcePanelResizing \? 'true' : 'false'\}/);
  assert.doesNotMatch(panel, /transition-\[flex-grow\]/);
  assert.doesNotMatch(message, /transition-all/);
});

test('assistant history and source surfaces stay mounted for reversible exits', () => {
  assert.match(presence, /setMounted\(true\)/);
  assert.match(presence, /setVisible\(false\)/);
  assert.match(presence, /window\.clearTimeout/);
  assert.match(page, /historyDrawerPresence\.mounted/);
  assert.match(page, /historySidebarPresence\.mounted/);
  assert.match(page, /data-state=\{historyDrawerPresence\.visible \? 'open' : 'closed'\}/);
  assert.match(page, /document\.body\.style\.overflow = 'hidden'/);
  assert.match(page, /desktopQuery\.matches\) setHistoryDrawerOpen\(false\)/);
  assert.match(page, /aria-modal="true"/);
  assert.match(page, /drawerOpenerRef/);
  assert.doesNotMatch(page, /transition-\[width/);
  assert.match(page, /historyDrawerPresence\.reducedMotion \? 'translate-x-0' : 'translate-x-6'/);
  assert.match(page, /historySidebarPresence\.reducedMotion \? 'translate-x-0' : '-translate-x-2'/);
  assert.match(sourceViewer, /presence\.mounted/);
  assert.match(sourceViewer, /presence\.reducedMotion \? '!translate-x-0'/);
  assert.doesNotMatch(`${panel}\n${page}`, /animate-in/);
});

test('source accordion supports variable-height reversal and removes hidden focus targets', () => {
  assert.match(sourceAccordion, /grid-rows-\[1fr\]/);
  assert.match(sourceAccordion, /grid-rows-\[0fr\]/);
  assert.match(sourceAccordion, /transition-\[grid-template-rows\]/);
  assert.match(sourceAccordion, /min-h-0 overflow-hidden/);
  assert.match(sourceAccordion, /inert=\{!expanded\}/);
  assert.doesNotMatch(sourceAccordion, /\shidden=\{!expanded\}/);
  assert.doesNotMatch(sourceAccordion, /max-h-/);
});

test('assistant source navigation makes every JavaScript scroll instant under reduced motion', () => {
  for (const viewer of [highlightExcerpt, pdfViewer, textViewer, spreadsheetViewer, htmlViewer]) {
    assert.match(viewer, /getReducedMotionPreference\(\) \? 'auto' : 'smooth'/);
    assert.doesNotMatch(viewer, /behavior: 'smooth'/);
  }
  assert.doesNotMatch(`${highlightExcerpt}\n${pdfViewer}`, /duration-700/);
});
