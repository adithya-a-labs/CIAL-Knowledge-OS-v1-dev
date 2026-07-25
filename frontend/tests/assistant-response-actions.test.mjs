import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const message = readFileSync(new URL('../src/components/assistant/ChatMessage.tsx', import.meta.url), 'utf8');
const panel = readFileSync(new URL('../src/components/assistant/ChatPanel.tsx', import.meta.url), 'utf8');
const adapter = readFileSync(new URL('../src/api/adapters.ts', import.meta.url), 'utf8');
const exportDialog = readFileSync(new URL('../src/components/assistant/ExportPreviewDialog.tsx', import.meta.url), 'utf8');
const workspacePage = readFileSync(new URL('../src/pages/WorkspacePage.tsx', import.meta.url), 'utf8');
const contextChips = readFileSync(new URL('../src/components/assistant/ContextChips.tsx', import.meta.url), 'utf8');
const corpusExplorer = readFileSync(new URL('../src/components/corpus/CorpusExplorer.tsx', import.meta.url), 'utf8');
const fileStatus = readFileSync(new URL('../src/components/documents/FileIndexingStatus.tsx', import.meta.url), 'utf8');
const statusHook = readFileSync(new URL('../src/hooks/useDocumentIndexingStatuses.ts', import.meta.url), 'utf8');
const documentWorkspace = readFileSync(new URL('../src/pages/DocumentWorkspacePage.tsx', import.meta.url), 'utf8');

test('copy uses the complete persisted Markdown answer and reports Copied', () => {
  assert.match(panel, /navigator\.clipboard\.writeText\(message\.content\)/);
  assert.match(message, /Copied/);
});

test('response actions use message-scoped APIs and stale generation guards', () => {
  assert.match(panel, /regenerateMessage\(message\.id\)/);
  assert.match(panel, /actionGenerationRef\.current\[message\.id\] !== generation/);
  assert.doesNotMatch(panel, /coming soon/);
});

test('explain simpler sends only the operation and message is appended atomically', () => {
  const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
  assert.match(client, /transformMessage\(messageId: string, operation:/);
  assert.match(client, /JSON\.stringify\(\{ operation \}\)/);
  assert.doesNotMatch(client.split('export function transformMessage', 2)[1].split('export function', 1)[0], /searchScope|selectedDocument|evidence|question/);
  assert.match(panel, /appendMessage\(actionSessionId, responseFromRecord\(record\)\)/);
  assert.match(panel, /actionGenerationRef\.current\[message\.id\] !== generation/);
});

test('explain simpler has message-scoped loading and accessible progress text', () => {
  assert.match(message, /Creating simpler explanation/);
  assert.match(message, /disabled=\{Boolean\(loadingAction\)\}/);
  assert.match(panel, /actionByMessage\[msg\.id\]/);
});

test('create checklist reuses the minimal transform request and accessible loading state', () => {
  const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
  const transformFunction = client.split('export function transformMessage', 2)[1].split('export function', 1)[0];
  assert.match(transformFunction, /JSON\.stringify\(\{ operation \}\)/);
  assert.doesNotMatch(transformFunction, /question|answer|searchScope|profile|selectedDocument|selectedFolder|chunk|citation|evidence/);
  assert.match(panel, /transformMessage\(message\.id, action\)/);
  assert.match(message, /Creating action checklist/);
  assert.match(message, /disabled=\{Boolean\(loadingAction\)\}/);
  assert.match(panel, /appendMessage\(actionSessionId, responseFromRecord\(record\)\)/);
});

test('metadata derives documents from source identity and separates citations', () => {
  assert.match(adapter, /new Set\(\[\.\.\.sources, \.\.\.citations\]/);
  assert.match(adapter, /citationCount: citations\.length/);
  assert.match(message, /evidence confidence/);
});

test('PDF and DOCX exports use exact persisted identifiers and never send answer content', () => {
  const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
  assert.match(panel, /session_id: actionSessionId, message_id: message\.id/);
  assert.match(panel, /action === 'export_pdf' \? 'pdf' : 'docx'/);
  const create = client.split('export function createAssistantExport', 2)[1].split('export function', 1)[0];
  assert.match(create, /'\/api\/exports'/);
  assert.doesNotMatch(create, /message\.content|answer_text|raw_html|evidence_text|citation_ids|source_records/);
});

test('export dialog polls backend state and never downloads automatically', () => {
  assert.match(exportDialog, /getAssistantExport\(exportId, controller\.signal\)/);
  assert.match(exportDialog, /window\.setTimeout\(poll, 900\)/);
  assert.match(exportDialog, /controller\.abort\(\)/);
  assert.match(exportDialog, /Confirm Download/);
  assert.match(exportDialog, /downloadLock\.current/);
  assert.doesNotMatch(exportDialog.split('useEffect(() =>', 2)[1], /anchor\.click\(\)/);
});

test('preview supports progress, cancellation, retry, format switch, and accessibility', () => {
  assert.match(exportDialog, /aria-live="polite"/);
  assert.match(exportDialog, /title="PDF export preview"/);
  assert.match(exportDialog, /title="DOCX Preview"/);
  assert.match(exportDialog, /sandbox=""/);
  assert.match(exportDialog, /Cancel/);
  assert.match(exportDialog, /Retry/);
  assert.match(exportDialog, /Switch to/);
});

test('ready exports expose an explicit editable Save to My Workspace confirmation', () => {
  assert.match(exportDialog, /ready\?<Button[^>]*onClick=\{beginWorkspaceSave\}/);
  assert.match(exportDialog, /suggested_workspace_filename/);
  assert.match(exportDialog, /value=\{workspaceFilename\}/);
  assert.match(exportDialog, /onChange=\{\(event\)=>setWorkspaceFilename/);
  assert.match(exportDialog, /Save to My Workspace/);
});

test('workspace save uses the typed endpoint once and prevents duplicate submissions', () => {
  const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');
  assert.match(client, /saveAssistantExportToWorkspace/);
  assert.match(client, /\/save-to-workspace/);
  assert.match(exportDialog, /saveLock\.current/);
  assert.match(exportDialog, /disabled=\{saving \|\| !workspaceFilename\.trim\(\)\}/);
  assert.doesNotMatch(exportDialog.split('confirmWorkspaceSave', 2)[1].split('const ready', 1)[0], /fetchAssistantExportArtifact|anchor\.click|uploadMyWorkspaceFiles/);
});

test('workspace save refreshes workspace queries and provides an open action', () => {
  assert.match(exportDialog, /invalidateQueries\(\{queryKey:\['my-workspace-tree'\]\}\)/);
  assert.match(exportDialog, /invalidateQueries\(\{queryKey:\['my-workspace-folder'\]\}\)/);
  assert.match(exportDialog, /invalidateQueries\(\{queryKey:\['my-workspace-summary'\]\}\)/);
  assert.match(exportDialog, /Saved to My Workspace/);
  assert.match(exportDialog, /savedDocument\.filename/);
  assert.match(exportDialog, /Open in My Workspace/);
  assert.match(exportDialog, /error instanceof Error\?error\.message/);
});

test('workspace automatically polls only while files are pending or indexing', () => {
  assert.match(workspacePage, /refetchInterval/);
  assert.match(workspacePage, /\['pending', 'indexing'\]\.includes\(file\.status\)/);
  assert.match(workspacePage, /\? 1500 : false/);
  assert.doesNotMatch(workspacePage, /button-index|Index now|Manual sync/);
});

test('chat attachments use the persistent managed upload and final document id', () => {
  assert.match(panel, /uploadChatAttachment\(file, activeSession\.id\)/);
  assert.match(panel, /backendDocumentId: result\.value\.document_id/);
  assert.match(panel, /backendDocumentVersionId: result\.value\.document_version_id/);
  assert.doesNotMatch(panel, /uploadDocument\(file/);
});

test('chat generation stays blocked until every attachment is indexed', () => {
  assert.match(panel, /blockingAttachments = effectiveUploadedFiles\.filter/);
  assert.match(panel, /file\.indexingStatus !== 'indexed'/);
  assert.match(panel, /if \(blockingAttachments\.length > 0\)/);
  assert.match(panel, /disabled=\{!input\.trim\(\) \|\| isLoading \|\| blockingAttachments\.length > 0\}/);
  const handler = panel.split(/const handleSend = async \([^)]*\) => \{/, 2)[1].split('const handleRegenerate', 1)[0];
  assert.ok(handler.indexOf('if (blockingAttachments.length > 0)') < handler.indexOf("setInput('')"));
});

test('shared file status renders stable accessible state icons across surfaces', () => {
  assert.match(fileStatus, /animate-spin motion-reduce:animate-none/);
  assert.match(fileStatus, /aria-label=\{`File status:/);
  assert.match(fileStatus, /aria-live=\{terminal \? 'polite' : 'off'\}/);
  for (const surface of [contextChips, workspacePage, corpusExplorer, exportDialog]) {
    assert.match(surface, /FileIndexingStatus/);
  }
  assert.match(contextChips, /uploadedFiles\.map/);
});

test('document status polling starts for active work and stops at terminal state', () => {
  assert.match(statusHook, /item\.indexing_status === 'pending' \|\| item\.indexing_status === 'indexing'/);
  assert.match(statusHook, /\? 1500 : false/);
  assert.match(statusHook, /retry: false/);
  assert.match(panel, /useDocumentIndexingStatuses/);
  assert.match(exportDialog, /useDocumentIndexingStatuses/);
});

test('failed status is a retry button only when the server allows it', () => {
  assert.match(fileStatus, /status === 'failed' && retryAllowed && Boolean\(documentId\)/);
  assert.match(fileStatus, /if \(canRetry\) return <button/);
  assert.match(fileStatus, /aria-label=\{label\}/);
  assert.match(fileStatus, /Retry indexing/);
  assert.match(fileStatus, /return <span/);
});

test('retry is single-flight and changes to queued only after a successful response', () => {
  assert.match(fileStatus, /requestLock\.current/);
  assert.match(fileStatus, /if \(!canRetry \|\| requestLock\.current/);
  assert.match(fileStatus, /const result = await retryDocumentIndexing\(documentId\)/);
  assert.ok(fileStatus.indexOf('setAccepted(true)') > fileStatus.indexOf('await retryDocumentIndexing(documentId)'));
  assert.match(fileStatus, /disabled=\{isRetrying\}/);
  assert.match(fileStatus, /toast\(\{ title: 'Indexing restarted' \}\)/);
  assert.match(fileStatus, /title: 'Indexing retry failed'/);
  assert.match(fileStatus, /error instanceof Error \? error\.message/);
});

test('retry refreshes status consumers and preserves reduced-motion loading', () => {
  assert.match(fileStatus, /invalidateQueries\(\{ queryKey: \['document-indexing-statuses'\] \}\)/);
  assert.match(fileStatus, /invalidateQueries\(\{ queryKey: \['my-workspace-folder'\] \}\)/);
  assert.match(fileStatus, /invalidateQueries\(\{ queryKey: \['corpus-folder'\] \}\)/);
  assert.match(fileStatus, /animate-spin motion-reduce:animate-none/);
});

test('shared retry status is wired across workspace, chat, context, corpus, exports, and document view', () => {
  for (const surface of [workspacePage, contextChips, corpusExplorer, exportDialog, documentWorkspace]) {
    assert.match(surface, /retryAllowed=/);
    assert.match(surface, /documentId=/);
  }
  assert.match(panel, /retryAllowed: status\.retry_allowed/);
});
