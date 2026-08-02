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
  SystemStatusResponse,
  AdminSystemMonitor,
  IndexStatusResponse,
  EnterpriseRepositoryRequest,
  EnterpriseRepositorySettings,
  LoginRequest,
  LogoutResponse,
  RebuildIndexResponse,
  SignupRequest,
  AuthResponse,
  ChatHistorySession,
  ChatSessionCreatePayload,
  GlobalSearchFilters,
  GlobalSearchResponse,
  RecentSearchList,
  SavedKnowledgeList,
  SavedKnowledgeRecord,
  NotebookArtifactRecord,
  NotebookChatBinding,
  NotebookRecord,
  NotebookSourceList,
} from './types';
import type { WorkspaceFile, WorkspaceFolderResponse, WorkspaceNote, WorkspaceNoteList, WorkspacePreferences, WorkspaceSummaryResponse, WorkspaceTreeResponse } from '@/data/workspace/workspaceTypes';
import { ApiError } from './types';

const CONFIGURED_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
export const AUTH_INVALIDATED_EVENT = 'cial-auth-invalidated';
const CHAT_REQUEST_TIMEOUT_MS = 150_000;
const SYSTEM_STATUS_TIMEOUT_MS = 8_000;
let authInvalidationDispatched = false;

type AuthInvalidationMode = 'none' | 'protected';
type ApiRequestInit = RequestInit & {
  authInvalidation?: AuthInvalidationMode;
};

function isLoopbackHost(hostname: string) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0' || hostname === '::1' || hostname === '[::1]';
}

function resolveApiBaseUrl() {
  if (!CONFIGURED_API_BASE_URL) return '';
  if (typeof window === 'undefined') {
    return CONFIGURED_API_BASE_URL;
  }
  try {
    const apiUrlValue = new URL(CONFIGURED_API_BASE_URL);
    const pageHostname = window.location.hostname;
    if (
      isLoopbackHost(apiUrlValue.hostname)
      && isLoopbackHost(pageHostname)
      && apiUrlValue.origin !== window.location.origin
    ) {
      return '';
    }
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
    const responseText = await response.text();
    let detail: unknown = responseText;
    try { detail = responseText ? JSON.parse(responseText) : null; } catch { /* retain the safe text response */ }
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

export function getSystemStatus(signal?: AbortSignal) {
  const boundedSignal = signal
    ? AbortSignal.any([signal, AbortSignal.timeout(SYSTEM_STATUS_TIMEOUT_MS)])
    : AbortSignal.timeout(SYSTEM_STATUS_TIMEOUT_MS);
  return request<SystemStatusResponse>('/api/system/status', {
    cache: 'no-store',
    signal: boundedSignal,
  });
}

export function getAdminSystemMonitor(signal?: AbortSignal) {
  return request<AdminSystemMonitor>('/api/admin/system/monitor', {
    cache: 'no-store',
    signal,
  });
}

export async function streamAdminSystemMonitor(
  onSnapshot: (snapshot: AdminSystemMonitor) => void,
  signal: AbortSignal,
  onConnected?: () => void,
) {
  const response = await fetch(apiUrl('/api/admin/system/stream'), {
    credentials: 'include',
    cache: 'no-store',
    headers: { Accept: 'text/event-stream' },
    signal,
  });
  if (!response.ok || !response.body) {
    throw new ApiError(
      response.status === 403
        ? 'System monitoring permission is required.'
        : `Monitor stream failed with status ${response.status}`,
      response.status,
      null,
    );
  }
  onConnected?.();
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? '';
    for (const frame of frames) {
      const data = frame
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n');
      if (data) onSnapshot(JSON.parse(data) as AdminSystemMonitor);
    }
    if (done) break;
  }
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

export function listNotebooks(signal?: AbortSignal) {
  return request<{ items: NotebookRecord[] }>('/api/notebooks', { signal });
}
export function getNotebook(id: string, signal?: AbortSignal) {
  return request<NotebookRecord>(`/api/notebooks/${encodeURIComponent(id)}`, { signal });
}
export function createNotebook(payload: { title: string; description?: string | null }) {
  return request<NotebookRecord>('/api/notebooks', { method: 'POST', body: JSON.stringify(payload) });
}
export function updateNotebook(id: string, payload: { title?: string; description?: string | null }) {
  return request<NotebookRecord>(`/api/notebooks/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) });
}
export async function deleteNotebook(id: string) {
  const response = await fetch(apiUrl(`/api/notebooks/${encodeURIComponent(id)}`), { method: 'DELETE', credentials: 'include' });
  if (!response.ok) throw new ApiError('Could not delete notebook.', response.status, null);
}
export function listNotebookSources(id: string, signal?: AbortSignal) {
  return request<NotebookSourceList>(`/api/notebooks/${encodeURIComponent(id)}/sources`, { signal });
}
export function attachNotebookSources(id: string, sources: Array<{ source_type: 'document' | 'note' | 'summary'; document_id?: string; note_id?: string; summary_artifact_id?: string; is_default_active?: boolean }>) {
  return request<NotebookSourceList>(`/api/notebooks/${encodeURIComponent(id)}/sources`, { method: 'POST', body: JSON.stringify({ sources }) });
}
export function updateNotebookSource(id: string, sourceId: string, isDefaultActive: boolean) {
  return request(`/api/notebooks/${encodeURIComponent(id)}/sources/${encodeURIComponent(sourceId)}`, { method: 'PATCH', body: JSON.stringify({ is_default_active: isDefaultActive }) });
}
export async function detachNotebookSource(id: string, sourceId: string) {
  const response = await fetch(apiUrl(`/api/notebooks/${encodeURIComponent(id)}/sources/${encodeURIComponent(sourceId)}`), { method: 'DELETE', credentials: 'include' });
  if (!response.ok) throw new ApiError('Could not detach source.', response.status, null);
}
export function getNotebookChatBinding(id: string, signal?: AbortSignal) {
  return request<NotebookChatBinding>(`/api/notebooks/${encodeURIComponent(id)}/chat-session`, { signal });
}
export function listNotebookArtifacts(id: string, signal?: AbortSignal) {
  return request<{ items: NotebookArtifactRecord[] }>(`/api/notebooks/${encodeURIComponent(id)}/artifacts`, { signal });
}
export function createNotebookArtifact(id: string, payload: { artifact_type: NotebookArtifactRecord['artifact_type']; title?: string; summary_length?: 'brief' | 'standard' | 'detailed'; custom_instructions?: string }) {
  return request<NotebookArtifactRecord>(`/api/notebooks/${encodeURIComponent(id)}/artifacts`, { method: 'POST', body: JSON.stringify(payload) });
}
export async function deleteNotebookArtifact(id: string, artifactId: string) {
  const response = await fetch(apiUrl(`/api/notebooks/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(artifactId)}`), { method: 'DELETE', credentials: 'include' });
  if (!response.ok) throw new ApiError('Could not delete artifact.', response.status, null);
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
    return request<WorkspaceFile>('/api/workspaces/me/documents/upload', { method: 'POST', body });
  }));
}

export function listMyNotes(params: { query?: string; filter?: string; cursor?: string | null; tagId?:string|null } = {}) {
  const query = new URLSearchParams(); if (params.query) query.set('query', params.query); if (params.filter) query.set('filter', params.filter); if (params.cursor) query.set('cursor', params.cursor);if(params.tagId)query.set('tag_id',params.tagId);
  return request<WorkspaceNoteList>(`/api/workspaces/me/notes${query.size ? `?${query}` : ''}`);
}
export function createMyNote(title = 'Untitled') { return request<WorkspaceNote>('/api/workspaces/me/notes', { method: 'POST', body: JSON.stringify({ title }) }); }
export function updateMyNote(id: string, payload: Partial<WorkspaceNote> & { expected_revision: number; force?: boolean }) { return request<WorkspaceNote>(`/api/workspaces/me/notes/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) }); }
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
  citations:Array<{citation_id:string;reference_id?:string;document_id:string|null;document_version_id?:string|null;note_id:string|null;page_number:number|null;section:string|null;chunk_id:string|null;excerpt:string|null;ordering?:number|null}>; stale:boolean;
  document_id?:string|null;document_version_id?:string|null;document_version_number?:number|null;
  structured_payload?:DocumentAnalysisPayload|null;citation_snapshot?:Array<Record<string,unknown>>;
  source_chunk_count?:number;source_token_count?:number;map_group_count?:number;model_name?:string|null;language?:string;
  generation_config?:Record<string,unknown>;provenance_hash?:string|null;progress?:AnalysisProgress;
  started_at?:string|null;updated_at?:string|null;error_code?:string|null;error_message?:string|null;retryable?:boolean;suggested_questions?:string[];
}
export type DocumentAnalysisType='overview'|'detailed'|'key_points'|'action_items';
export type DocumentAnalysisLength='brief'|'standard'|'detailed';
export interface GroundedAnalysisItem{text:string;citation_ids:string[]}
export interface DocumentAnalysisPayload{title:string;document_type:'general'|'calendar'|'policy'|'standard'|'contract'|'report';overview?:GroundedAnalysisItem[];sections:Array<{heading:string;items:GroundedAnalysisItem[]}>;key_findings:GroundedAnalysisItem[];important_dates:GroundedAnalysisItem[];requirements:GroundedAnalysisItem[];action_items:GroundedAnalysisItem[];coverage_gaps:string[];citation_ids:string[];suggested_questions:string[]}
export interface AnalysisProgress{
  stage:string;completed:number;total:number;message:string;
  map_completed?:number;map_total?:number;reduce_level?:number|null;reduce_group?:number|null;
  reduce_total_groups?:number|null;model_calls?:number;repair_calls?:number;retries?:number;
  elapsed_ms?:number;source_chunks_processed?:number;source_chunks_total?:number;
  checkpoint_reuse?:number;background_message?:string;
}
export interface DocumentAnalysisList{document_id:string;current_version_id:string;summary_type:string;length:string;current:SummaryRecord|null;previous:SummaryRecord[]}
export interface DocumentAnalysisCreateResponse{disposition:'reused'|'queued'|'running'|'completed';summary:SummaryRecord}
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
export function getDocumentAnalysis(documentId:string,summaryType:DocumentAnalysisType='overview',length:DocumentAnalysisLength='standard',signal?:AbortSignal){const query=new URLSearchParams({summary_type:summaryType,length});return request<DocumentAnalysisList>(`/api/documents/${encodeURIComponent(documentId)}/analysis?${query}`,{signal});}
export function createDocumentAnalysis(documentId:string,payload:{summary_type:DocumentAnalysisType;length:DocumentAnalysisLength;force_regenerate?:boolean;language?:string}){return request<DocumentAnalysisCreateResponse>(`/api/documents/${encodeURIComponent(documentId)}/analysis`,{method:'POST',body:JSON.stringify(payload)});}
export function getDocumentAnalysisStatus(id:string,signal?:AbortSignal){return request<SummaryRecord>(`/api/summaries/${encodeURIComponent(id)}/status`,{signal});}
export function cancelDocumentAnalysis(id:string){return request<SummaryRecord>(`/api/summaries/${encodeURIComponent(id)}/cancel`,{method:'POST'});}
export function listSavedKnowledge(params:{query?:string;favorite?:boolean;collection?:string}={}){const query=new URLSearchParams();if(params.query)query.set('query',params.query);if(params.favorite)query.set('favorite','true');if(params.collection)query.set('collection',params.collection);return request<SavedKnowledgeList>(`/api/saved-knowledge${query.size?`?${query}`:''}`);}
export function getSavedKnowledge(id:string){return request<SavedKnowledgeRecord>(`/api/saved-knowledge/${encodeURIComponent(id)}`);}
export function saveAnswerToKnowledge(payload:{message_id:string;title:string;collection?:string|null;tags:string[];description?:string|null;save_citations:boolean;save_original_question:boolean;save_conversation_context:boolean}){return request<SavedKnowledgeRecord>('/api/saved-knowledge',{method:'POST',body:JSON.stringify(payload)});}
export function updateSavedKnowledge(id:string,payload:{expected_version:number;title?:string;collection?:string|null;tags?:string[];description?:string|null;is_favorite?:boolean;state?:'active'|'archived'}){return request<SavedKnowledgeRecord>(`/api/saved-knowledge/${encodeURIComponent(id)}`,{method:'PATCH',body:JSON.stringify(payload)});}
export function duplicateSavedKnowledge(id:string){return request<SavedKnowledgeRecord>(`/api/saved-knowledge/${encodeURIComponent(id)}/duplicate`,{method:'POST'});}
export function convertSavedKnowledgeToNote(id:string){return request<WorkspaceNote>(`/api/saved-knowledge/${encodeURIComponent(id)}/convert-to-note`,{method:'POST'});}
export async function removeSavedKnowledge(id:string){const response=await fetch(apiUrl(`/api/saved-knowledge/${encodeURIComponent(id)}`),{method:'DELETE',credentials:'include'});if(!response.ok)throw new ApiError('Could not remove saved item.',response.status,null);}

export function createChatSession(payload:ChatSessionCreatePayload){return request<ChatHistorySession>('/api/chat/sessions',{method:'POST',body:JSON.stringify(payload)});}
export function globalSearch(payload:{query:string;mode:'instant'|'full';filters:GlobalSearchFilters;cursor?:string|null;limit?:number;interpret?:boolean},signal?:AbortSignal){return request<GlobalSearchResponse>('/api/search',{method:'POST',body:JSON.stringify(payload),signal});}
export function listRecentSearches(){return request<RecentSearchList>('/api/search/recent');}
export async function clearRecentSearches(id?:string){const response=await fetch(apiUrl(id?`/api/search/recent/${encodeURIComponent(id)}`:'/api/search/recent'),{method:'DELETE',credentials:'include'});if(!response.ok)throw new ApiError('Could not clear search history.',response.status,null);}

export function askQuestion(payload: ChatRequest, signal?: AbortSignal) {
  const boundedSignal = signal
    ? AbortSignal.any([signal, AbortSignal.timeout(CHAT_REQUEST_TIMEOUT_MS)])
    : AbortSignal.timeout(CHAT_REQUEST_TIMEOUT_MS);
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal: boundedSignal,
  });
}

export async function streamQuestion(
  payload: ChatRequest,
  onEvent: (event: import('./types').GenerationEvent) => void,
  signal?: AbortSignal,
  onConnected?: () => void,
) {
  const timeoutMs = CHAT_REQUEST_TIMEOUT_MS;
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort(signal?.reason);
  if (signal?.aborted) abortFromCaller(); else signal?.addEventListener('abort', abortFromCaller, { once: true });
  const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  try {
    const response = await fetch(apiUrl('/api/chat/stream'), { method: 'POST', credentials: 'include', signal: controller.signal,
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!response.ok || !response.body) {
      let detail: unknown = null;
      try { detail = await response.json(); } catch { detail = await response.text(); }
      const nested = detail && typeof detail === 'object' && 'detail' in detail
        ? (detail as { detail?: unknown }).detail
        : detail;
      const message = nested && typeof nested === 'object' && 'message' in nested
        ? String((nested as { message?: unknown }).message || `Request failed with status ${response.status}`)
        : `Request failed with status ${response.status}`;
      throw new ApiError(message, response.status, detail);
    }
    onConnected?.();
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let result: import('./types').ChatResponse | null = null;
    while (true) {
      const { value, done } = await reader.read(); buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split('\n'); buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line) as import('./types').GenerationEvent; onEvent(event);
        if (event.type === 'result') result = event.payload as import('./types').ChatResponse;
        if (event.type === 'error') {
          const failure = event.payload as {
            message?: string;
            failed_stage?: string | null;
            reason?: string | null;
          };
          const failedStage = failure?.failed_stage?.replaceAll('_', ' ');
          const detail = failedStage
            ? ` Failed stage: ${failedStage}${failure.reason ? ` (${failure.reason})` : ''}.`
            : '';
          throw new Error(
            `${failure?.message || 'Generation failed.'}${detail}`,
          );
        }
        if (event.type === 'cancelled') throw new DOMException('Generation stopped', 'AbortError');
      }
      if (done) break;
    }
    if (!result) throw new Error('The generation stream ended before a result was received.');
    return result;
  } catch (error) {
    if (timedOut) {
      const timeout = new Error('The assistant request timed out. Please retry.');
      timeout.name = 'TimeoutError';
      throw timeout;
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener('abort', abortFromCaller);
  }
}

export function listChatSessions(signal?: AbortSignal) {
  return request<import('./types').ChatHistoryList>('/api/chat/sessions', { signal });
}

export function regenerateMessage(messageId: string, signal?: AbortSignal) {
  const boundedSignal = signal
    ? AbortSignal.any([signal, AbortSignal.timeout(CHAT_REQUEST_TIMEOUT_MS)])
    : AbortSignal.timeout(CHAT_REQUEST_TIMEOUT_MS);
  return request<ChatResponse>(`/api/chat/messages/${encodeURIComponent(messageId)}/regenerate`, { method: 'POST', signal: boundedSignal });
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
    body: JSON.stringify({ force, confirm: true }),
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
