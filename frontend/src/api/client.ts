import type {
  ApiDocument,
  ChatRequest,
  ChatResponse,
  CorpusDocument,
  CorpusFolderResponse,
  CorpusSyncResponse,
  CorpusTreeResponse,
  DocumentPreview,
  DocumentListResponse,
  EvaluationRunRequest,
  EvaluationRunResponse,
  EvaluationRunsResponse,
  ExportListResponse,
  HealthResponse,
  IndexStatusResponse,
  EnterpriseRepositoryRequest,
  EnterpriseRepositorySettings,
  LoginRequest,
  LogoutResponse,
  RebuildIndexResponse,
  SignupRequest,
  AuthResponse,
} from './types';
import type { WorkspaceFolderResponse, WorkspaceNote, WorkspaceNoteList, WorkspacePreferences, WorkspaceSummaryResponse, WorkspaceTreeResponse } from '@/data/workspace/workspaceTypes';
import { ApiError } from './types';

const CONFIGURED_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');
export const AUTH_INVALIDATED_EVENT = 'cial-auth-invalidated';
let authInvalidationDispatched = false;

type AuthInvalidationMode = 'none' | 'protected';
type ApiRequestInit = RequestInit & {
  authInvalidation?: AuthInvalidationMode;
};

function isLoopbackHost(hostname: string) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0' || hostname === '::1' || hostname === '[::1]';
}

function resolveApiBaseUrl() {
  if (typeof window === 'undefined') {
    return CONFIGURED_API_BASE_URL;
  }
  try {
    const apiUrlValue = new URL(CONFIGURED_API_BASE_URL);
    const pageHostname = window.location.hostname;
    if (isLoopbackHost(apiUrlValue.hostname) && pageHostname && apiUrlValue.hostname !== pageHostname) {
      apiUrlValue.hostname = pageHostname;
      return apiUrlValue.toString().replace(/\/$/, '');
    }
  } catch {
    return CONFIGURED_API_BASE_URL;
  }
  return CONFIGURED_API_BASE_URL;
}

export function apiUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${resolveApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`;
}

export function resetAuthInvalidationGuard() {
  authInvalidationDispatched = false;
}

async function request<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { authInvalidation = 'protected', ...fetchInit } = init;
  const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
    credentials: 'include',
    ...fetchInit,
    headers: {
      ...(fetchInit.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...fetchInit.headers,
    },
  });

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const rawDetail =
      typeof detail === 'object' && detail !== null && 'detail' in detail
        ? (detail as { detail: unknown }).detail
        : detail;
    const message =
      typeof rawDetail === 'object' && rawDetail !== null && 'message' in rawDetail
        ? String((rawDetail as { message: unknown }).message)
        : typeof rawDetail === 'string'
          ? rawDetail
          : `Request failed with status ${response.status}`;
    if (
      response.status === 401 &&
      authInvalidation === 'protected' &&
      typeof window !== 'undefined' &&
      !authInvalidationDispatched
    ) {
      authInvalidationDispatched = true;
      window.dispatchEvent(new Event(AUTH_INVALIDATED_EVENT));
    }
    throw new ApiError(message, response.status, detail);
  }

  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<HealthResponse>('/api/health', { cache: 'no-store', authInvalidation: 'none' });
}

export function signUp(payload: SignupRequest) {
  return request<AuthResponse>('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify(payload),
    authInvalidation: 'none',
  });
}

export function logIn(payload: LoginRequest) {
  return request<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
    authInvalidation: 'none',
  });
}

export function getCurrentUser() {
  return request<AuthResponse>('/api/auth/me', { authInvalidation: 'none' });
}

export function logOut() {
  return request<LogoutResponse>('/api/auth/logout', {
    method: 'POST',
    authInvalidation: 'none',
  });
}

export function getMyWorkspaceTree() {
  return request<WorkspaceTreeResponse>('/api/workspaces/me/tree');
}

export function getMyWorkspaceFolder(folderId?: string | null) {
  return request<WorkspaceFolderResponse>(folderId ? `/api/workspaces/me/folders/${folderId}` : '/api/workspaces/me/root');
}

export function getMyWorkspaceSummary() {
  return request<WorkspaceSummaryResponse>('/api/workspaces/me/summary');
}

export function getMyWorkspacePreferences() {
  return request<WorkspacePreferences>('/api/workspaces/me/preferences');
}

export function saveMyWorkspacePreferences(preferences: WorkspacePreferences) {
  return request<WorkspacePreferences>('/api/workspaces/me/preferences', { method: 'PATCH', body: JSON.stringify(preferences) });
}

export function resetMyWorkspacePreferences() {
  return request<WorkspacePreferences>('/api/workspaces/me/preferences/reset', { method: 'POST' });
}

export function createMyWorkspaceFolder(name: string, parentId?: string | null) {
  return request('/api/workspaces/me/folders', { method: 'POST', body: JSON.stringify({ name, parent_id: parentId ?? null }) });
}

export function uploadMyWorkspaceFiles(files: File[], folderId?: string | null) {
  return Promise.all(files.map((file) => {
    const body = new FormData();
    body.append('file', file);
    if (folderId) body.append('folder_id', folderId);
    return request('/api/workspaces/me/documents/upload', { method: 'POST', body });
  }));
}

export function listMyNotes(params: { query?: string; filter?: string; cursor?: string | null; tagId?:string|null } = {}) {
  const query = new URLSearchParams(); if (params.query) query.set('query', params.query); if (params.filter) query.set('filter', params.filter); if (params.cursor) query.set('cursor', params.cursor);if(params.tagId)query.set('tag_id',params.tagId);
  return request<WorkspaceNoteList>(`/api/workspaces/me/notes${query.size ? `?${query}` : ''}`);
}
export function createMyNote(title = 'Untitled') { return request<WorkspaceNote>('/api/workspaces/me/notes', { method: 'POST', body: JSON.stringify({ title }) }); }
export function updateMyNote(id: string, payload: Partial<WorkspaceNote> & { expected_revision: number }) { return request<WorkspaceNote>(`/api/workspaces/me/notes/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) }); }
export async function deleteMyNote(id: string) { const response = await fetch(apiUrl(`/api/workspaces/me/notes/${encodeURIComponent(id)}`), { method: 'DELETE', credentials: 'include' }); if (!response.ok) throw new ApiError('Could not delete note.', response.status, null); }
export function restoreMyNote(id: string) { return request<WorkspaceNote>(`/api/workspaces/me/notes/${encodeURIComponent(id)}/restore`, { method: 'POST' }); }
export function duplicateMyNote(id: string) { return request<WorkspaceNote>(`/api/workspaces/me/notes/${encodeURIComponent(id)}/duplicate`, { method: 'POST' }); }
export function getNoteExportUrl(id: string) { return apiUrl(`/api/workspaces/me/notes/${encodeURIComponent(id)}/export?format=markdown`); }
export function listNoteTags(){return request<{items:Array<{id:string;name:string;color?:string|null;count:number}>}>('/api/workspaces/me/note-tags');}
export function createNoteTag(name:string,color?:string){return request<{id:string;name:string;color?:string|null}>('/api/workspaces/me/note-tags',{method:'POST',body:JSON.stringify({name,color:color??null})});}
export function renameNoteTag(id:string,name:string,color?:string){return request<{id:string;name:string;color?:string|null}>(`/api/workspaces/me/note-tags/${encodeURIComponent(id)}`,{method:'PATCH',body:JSON.stringify({name,color:color??null})});}
export async function deleteNoteTag(id:string){const response=await fetch(apiUrl(`/api/workspaces/me/note-tags/${encodeURIComponent(id)}`),{method:'DELETE',credentials:'include'});if(!response.ok)throw new ApiError('Could not delete tag.',response.status,null);}
export function addNoteTag(noteId:string,tagId:string){return request<WorkspaceNote>(`/api/workspaces/me/notes/${encodeURIComponent(noteId)}/tags/${encodeURIComponent(tagId)}`,{method:'POST'});}
export async function removeNoteTag(noteId:string,tagId:string){const response=await fetch(apiUrl(`/api/workspaces/me/notes/${encodeURIComponent(noteId)}/tags/${encodeURIComponent(tagId)}`),{method:'DELETE',credentials:'include'});if(!response.ok)throw new ApiError('Could not remove tag.',response.status,null);}
export function linkNoteDocument(noteId:string,documentId:string){return request<WorkspaceNote>(`/api/workspaces/me/notes/${encodeURIComponent(noteId)}/documents`,{method:'POST',body:JSON.stringify({document_id:documentId})});}
export async function unlinkNoteDocument(noteId:string,documentId:string){const response=await fetch(apiUrl(`/api/workspaces/me/notes/${encodeURIComponent(noteId)}/documents/${encodeURIComponent(documentId)}`),{method:'DELETE',credentials:'include'});if(!response.ok)throw new ApiError('Could not unlink document.',response.status,null);}

export interface SummaryRecord {
  id:string; title:string; summary_type:string; summary_length:string; multi_document_mode:string; status:string; content_markdown:string|null;
  citation_count:number; document_count:number; prompt_name:string; prompt_version:string; created_at:string; completed_at:string|null;
  sources:Array<{id:string;source_type:string;source_id:string|null;title:string;version_id:string|null}>;
  citations:Array<{citation_id:string;document_id:string|null;note_id:string|null;page_number:number|null;section:string|null;chunk_id:string|null;excerpt:string|null}>; stale:boolean;
}
export interface SummaryCreatePayload { sources:Array<{source_type:'document'|'folder'|'note'|'conversation'|'pasted_text';source_id?:string|null;title?:string|null;content?:string|null}>; summary_type:'executive'|'detailed'|'key_points'|'action_items'; summary_length:'brief'|'standard'|'detailed'; multi_document_mode:'together'|'separate'|'compare'; custom_instructions?:string|null; }
export interface SummaryStreamEvent { request_id:string; type:'stage'|'token'|'result'|'error'|'cancelled'; stage_id:string; status:string; metrics?:Record<string,number|string>; delta?:string; payload?:SummaryRecord|{message?:string}; }
export async function streamSummary(payload: SummaryCreatePayload,onEvent:(event:SummaryStreamEvent)=>void,signal?:AbortSignal) {
  const response=await fetch(apiUrl('/api/summaries/stream'),{method:'POST',credentials:'include',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(!response.ok||!response.body)throw new ApiError(`Summary request failed with status ${response.status}`,response.status,null);
  const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='';let result:SummaryRecord|null=null;
  while(true){const {value,done}=await reader.read();buffer+=decoder.decode(value,{stream:!done});const lines=buffer.split('\n');buffer=lines.pop()??'';for(const line of lines){if(!line.trim())continue;const event=JSON.parse(line) as SummaryStreamEvent;onEvent(event);if(event.type==='result')result=event.payload as SummaryRecord;if(event.type==='error')throw new Error((event.payload as {message?:string})?.message||'Summary generation failed.');}if(done)break;}
  if(!result)throw new Error('Summary stream ended without an artifact.');return result;
}
export function saveSummaryToNote(id:string,title?:string){return request<WorkspaceNote>(`/api/summaries/${encodeURIComponent(id)}/save-to-note`,{method:'POST',body:JSON.stringify({title:title??null})});}
export function getSummary(id:string){return request<SummaryRecord>(`/api/summaries/${encodeURIComponent(id)}`);}
export function getSummaryExportUrl(id:string,format:'markdown'|'pdf'|'docx'='markdown'){return apiUrl(`/api/summaries/${encodeURIComponent(id)}/export?format=${format}`);}
export function saveSummaryToSavedKnowledge(id:string){return request<{id:string;summary_id:string;title:string}>(`/api/summaries/${encodeURIComponent(id)}/save-to-saved-knowledge`,{method:'POST'});}
export function askSummaryFollowUp(id:string,mode:'original_versions'|'latest_versions'='original_versions'){return request<{chat_session_id:string;url:string;sources:Array<{source_type:string;source_id:string|null;title:string}>}>(`/api/summaries/${encodeURIComponent(id)}/ask-follow-up`,{method:'POST',body:JSON.stringify({mode})});}
export function listSavedKnowledge(){return request<{items:Array<{id:string;summary_id:string;title:string;source_count:number;created_at:string}>}>('/api/saved-knowledge');}
export async function removeSavedKnowledge(id:string){const response=await fetch(apiUrl(`/api/saved-knowledge/${encodeURIComponent(id)}`),{method:'DELETE',credentials:'include'});if(!response.ok)throw new ApiError('Could not remove saved item.',response.status,null);}

export function askQuestion(payload: ChatRequest, signal?: AbortSignal) {
  // Chat generation deliberately has no deadline. The caller supplies a
  // per-request signal solely for an explicit user Stop action.
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  });
}

export async function streamQuestion(payload: ChatRequest, onEvent: (event: import('./types').GenerationEvent) => void, signal?: AbortSignal) {
  const response = await fetch(apiUrl('/api/chat/stream'), { method: 'POST', credentials: 'include', signal,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok || !response.body) throw new ApiError(`Request failed with status ${response.status}`, response.status, null);
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let result: import('./types').ChatResponse | null = null;
  while (true) {
    const { value, done } = await reader.read(); buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split('\n'); buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line) as import('./types').GenerationEvent; onEvent(event);
      if (event.type === 'result') result = event.payload as import('./types').ChatResponse;
      if (event.type === 'error') throw new Error((event.payload as { message?: string })?.message || 'Generation failed.');
      if (event.type === 'cancelled') throw new DOMException('Generation stopped', 'AbortError');
    }
    if (done) break;
  }
  if (!result) throw new Error('The generation stream ended before a result was received.');
  return result;
}

export function listChatSessions(signal?: AbortSignal) {
  return request<import('./types').ChatHistoryList>('/api/chat/sessions', { signal });
}

export function regenerateMessage(messageId: string, signal?: AbortSignal) {
  return request<ChatResponse>(`/api/chat/messages/${encodeURIComponent(messageId)}/regenerate`, { method: 'POST', signal });
}

export function transformMessage(messageId: string, operation: 'explain_simpler' | 'create_checklist') {
  return request<import('./types').ChatHistoryMessage>(`/api/chat/messages/${encodeURIComponent(messageId)}/transform`, { method: 'POST', body: JSON.stringify({ operation }) });
}

export function toggleMessageFeedback(messageId: string, feedback: string) {
  return request<import('./types').MessageFeedbackResponse>(`/api/chat/messages/${encodeURIComponent(messageId)}/feedback`, { method: 'PUT', body: JSON.stringify({ feedback }) });
}

export function createAssistantExport(payload: { format: import('./types').AssistantExportFormat; session_id: string; message_id: string; title: string }) {
  return request<import('./types').AssistantExportCreateResponse>('/api/exports', { method: 'POST', body: JSON.stringify({ ...payload, options: { include_sources: true, include_generated_timestamp: true, include_conversation_context: false, page_size: 'A4', document_style: 'professional' } }) });
}
export function getAssistantExport(exportId: string, signal?: AbortSignal) {
  return request<import('./types').AssistantExportJob>(`/api/exports/${encodeURIComponent(exportId)}`, { signal });
}
export function saveAssistantExportToWorkspace(exportId: string, payload: import('./types').AssistantExportWorkspaceSaveRequest) {
  return request<import('./types').AssistantExportWorkspaceSaveResponse>(`/api/exports/${encodeURIComponent(exportId)}/save-to-workspace`, { method: 'POST', body: JSON.stringify(payload) });
}
export async function cancelAssistantExport(exportId: string) {
  const response = await fetch(apiUrl(`/api/exports/${encodeURIComponent(exportId)}`), { method: 'DELETE', credentials: 'include' });
  if (!response.ok) throw new ApiError(`Cancel failed with status ${response.status}`, response.status, null);
}
export async function fetchAssistantExportArtifact(path: string, signal?: AbortSignal) {
  const response = await fetch(apiUrl(path), { credentials: 'include', signal });
  if (!response.ok) throw new ApiError(`Export request failed with status ${response.status}`, response.status, null);
  return response;
}

export function getCorpusTree() {
  return request<CorpusTreeResponse>('/api/corpus/tree');
}

export function getCorpusFolder(path = '') {
  const query = path ? `?path=${encodeURIComponent(path)}` : '';
  return request<CorpusFolderResponse>(`/api/corpus/folder${query}`);
}

export function getCorpusDocument(id: string) {
  return request<CorpusDocument>(`/api/corpus/document/${encodeURIComponent(id)}`);
}

export function getDocumentFileUrl(documentId: string) {
  return apiUrl(`/api/corpus/document/${encodeURIComponent(documentId)}/file`);
}

export function getDocumentViewUrl(documentId: string) {
  return apiUrl(`/api/corpus/document/${encodeURIComponent(documentId)}/view`);
}

export function getDocumentDownloadUrl(documentId: string) {
  return apiUrl(`/api/corpus/document/${encodeURIComponent(documentId)}/download`);
}

export function getDocumentThumbnailUrl(documentId: string, page = 1) {
  return apiUrl(`/api/corpus/document/${encodeURIComponent(documentId)}/thumbnail?page=${encodeURIComponent(String(page))}`);
}

export function getDocumentPreview(
  documentId: string,
  options: {
    chunkId?: string;
    page?: number;
    sheetName?: string;
    sheetIndex?: number;
    slideNumber?: number;
  } = {},
) {
  const params = new URLSearchParams();
  if (options.chunkId) params.set('chunk_id', options.chunkId);
  if (options.page !== undefined) params.set('page', String(options.page));
  if (options.sheetName) params.set('sheet_name', options.sheetName);
  if (options.sheetIndex !== undefined) params.set('sheet_index', String(options.sheetIndex));
  if (options.slideNumber !== undefined) params.set('slide_number', String(options.slideNumber));
  const query = params.toString();
  return request<DocumentPreview>(
    `/api/corpus/document/${encodeURIComponent(documentId)}/preview${query ? `?${query}` : ''}`,
  );
}

export function syncCorpus() {
  return request<CorpusSyncResponse>('/api/corpus/sync', { method: 'POST' });
}

export function listDocuments() {
  return request<DocumentListResponse>('/api/documents');
}

export function uploadDocument(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return request<ApiDocument>('/api/documents/upload', {
    method: 'POST',
    body: formData,
  });
}

export function uploadChatAttachment(file: File, sessionId?: string) {
  const body = new FormData(); body.append('file', file);
  if (sessionId) body.append('session_id', sessionId);
  return request<import('./types').ChatAttachmentResponse>('/api/chat/attachments', { method: 'POST', body });
}

export function getDocumentIndexingStatus(documentId: string, signal?: AbortSignal) {
  return request<import('./types').DocumentIndexingStatus>(`/api/documents/${encodeURIComponent(documentId)}/indexing-status`, { signal });
}

export function retryDocumentIndexing(documentId: string) {
  return request<import('./types').DocumentIndexingStatus>(`/api/documents/${encodeURIComponent(documentId)}/retry-indexing`, { method: 'POST' });
}

export function rebuildIndex(force: boolean) {
  return request<RebuildIndexResponse>('/api/index/rebuild', {
    method: 'POST',
    body: JSON.stringify({ force }),
  });
}

export function getIndexStatus() {
  return request<IndexStatusResponse>('/api/index/status');
}

export function getEnterpriseRepositorySettings() {
  return request<EnterpriseRepositorySettings>('/api/settings/enterprise-repository');
}

export function validateEnterpriseRepository(payload: EnterpriseRepositoryRequest) {
  return request<EnterpriseRepositorySettings>('/api/settings/enterprise-repository/validate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function saveEnterpriseRepository(payload: EnterpriseRepositoryRequest) {
  return request<EnterpriseRepositorySettings>('/api/settings/enterprise-repository', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function runEvaluation(payload: EvaluationRunRequest) {
  return request<EvaluationRunResponse>('/api/evaluation/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listEvaluationRuns() {
  return request<EvaluationRunsResponse>('/api/evaluation/runs');
}

export function listExports() {
  return request<ExportListResponse>('/api/exports');
}
